      program ft

      implicit none

      include 'mpif.h'
      include 'global.h'
      integer i, ierr
      
c---------------------------------------------------------------------
c u0, u1, u2 are the main arrays in the problem. 
c Depending on the decomposition, these arrays will have different 
c dimensions. To accomodate all possibilities, we allocate them as 
c one-dimensional arrays and pass them to subroutines for different 
c views
c  - u0 contains the initial (transformed) initial condition
c  - u1 and u2 are working arrays
c---------------------------------------------------------------------

      double precision, allocatable :: u0(:), u1(:)
c---------------------------------------------------------------------
c Large arrays are in common so that they are allocated on the
c heap rather than the stack. This common block is not
c referenced directly anywhere else. Padding is to avoid accidental 
c cache problems, since all array sizes are powers of two.
c---------------------------------------------------------------------

      integer iter
      interface
          subroutine init(u0, u1)
          double precision, allocatable :: u0(:), u1(:)
          end subroutine init
      
          subroutine output_timers(title, n, timers)
          character title*(*)
          integer n, timers(:)
          end subroutine output_timers
  
          subroutine transpose_xy_z(xin, xout, timers)
          include 'global.h'
          double precision xin(ntdivnp), xout(ntdivnp)
          integer timers(:)
          end subroutine transpose_xy_z

      end interface

      call MPI_Init(ierr)

c---------------------------------------------------------------------
c Run the entire problem once to make sure all data is touched. 
c This reduces variable startup costs, which is important for such a 
c short benchmark. The other NPB 2 implementations are similar. 
c---------------------------------------------------------------------
      T_max = 0
      do i = 1, 4
         T_max = T_max+1
         T_warm(i) = T_max
      enddo
      do i = 1, 4
         T_max = T_max+1
         T_trans(i) = T_max
      enddo

      call setup()
      call init(u0, u1)

      if (outputMatrix .gt. 0) then
          write(fout, 5010)
5010      format('initial matrix:')
          call output_matrix(nx, ny, nz/np, u0)
      endif
      
      call MPI_Barrier(MPI_COMM_WORLD, ierr)
      call transpose_xy_z(u0, u1, T_warm)
      call MPI_Barrier(MPI_COMM_WORLD, ierr)
      call check_result(u1)

      if (outputMatrix .gt. 0) then
          write(fout, 5020)
5020      format('after transpose_xy_z:')
          call output_matrix(nz, nx, ny/np, u1)
      endif

      outputMatrix = 0

      do iter = 1, niter
         call init_matrix(u0)
         call MPI_Barrier(MPI_COMM_WORLD, ierr)
         call transpose_xy_z(u0, u1, T_trans)
         call MPI_Barrier(MPI_COMM_WORLD, ierr)
         call check_result(u1)
      enddo

      call MPI_Finalize(ierr)

      call output_timers('T_warm', 4, T_warm)
      call output_timers('T_trans', 4, T_trans)

      close(fout)
      end


c---------------------------------------------------------------------
c---------------------------------------------------------------------

      subroutine init_matrix(matrix)
      implicit none
      include 'global.h'
      double precision matrix(ntdivnp)
      double precision base
      integer i
      base = ntdivnp
      base = base * me
      do i = 1, ntdivnp
          matrix(i) = base
          base = base + 1
      enddo
      return
      end

      subroutine check_result(matrix)
      implicit none
      include 'global.h'
      double precision matrix(nz, nx, ny/np)
      double precision correct, diff
      integer x, y, yy, z, ierr
      yy = ny/np * me
      do y = 1, ny/np
        do x = 1, nx
          do z = 1, nz
            correct = z-1
            correct = correct*(nx*ny) + yy*nx + x-1
            diff = matrix(z, x, y) - correct
            if (diff .lt. 0) diff = -diff
            if (diff > 1e-6) then
              write(*, 20010) me, x, y, z, matrix(z, x, y), correct
20010         format(I0, ': Wrong result! x=', I0, ' y=', I0, ' z=', I0,
     >        ' num=', F0.0, ' correct=', F0.0)
              write(fout, 20020) x, y, z, matrix(z, x, y), correct
20020         format('Wrong result! x=', I0, ' y=', I0, ' z=', I0,
     >        ' num=', F0.0, ' correct=', F0.0)
              close(fout)
              call MPI_Finalize(ierr)
              call exit(555)
            endif
          enddo
        enddo
        yy = yy + 1
      enddo
      return
      end


      subroutine init(u0, u1)
      implicit none
      double precision, allocatable :: u0(:), u1(:)
      include 'global.h'

      ntdivnp = nx*ny*(nz/np)
      if (.not.allocated(u0)) allocate( u0(ntdivnp+3) )
      if (.not.allocated(u1)) allocate( u1(ntdivnp+3) )
      call init_matrix(u0)
      return
      end

      subroutine output_timers(title, n, timers)
      implicit none
      include 'global.h'
      character title*(*)
      integer n, timers(:)
      integer i
      double precision t

      write(fout, 1010) title
1010  format(A, ':')

      do i = 1, n
          t = timer_read(timers(i))
          write(fout, 1030) t
1030      format(' ', F16.5)
      enddo

      return
      end

      subroutine output_matrix(nnx, nny, nnz, matrix)
      implicit none
      include 'global.h'
      double precision matrix(nnx, nny, nnz)
      integer nnx, nny, nnz, x, y, z

6000  format('')
      do z = 1, nnz
          do y = 1, nny
              do x = 1, nnx
                  write(fout, 6010, advance='no') matrix(x, y, z)
6010              format(F4.0, ' ')
              enddo
              write(fout, 6000)
          enddo
          write(fout, 6000)
      enddo

      return
      end



      subroutine setup
      implicit none
      include 'mpinpb.h'
      include 'global.h'

      integer ierr, i, j, fstatus
      integer argc
      character(1024) arg
      character(1024) fname

      external iargc
      integer iargc

      call MPI_Comm_size(MPI_COMM_WORLD, np, ierr)
      call MPI_Comm_rank(MPI_COMM_WORLD, me, ierr)

      dc_type = MPI_DOUBLE

      argc = iargc()
      if (argc .lt. 3) then
         call getarg(0, arg)
         write(*, 238) arg
 238     format('Usage: mpirun -np <nproc> ', A,
     >    ' nx ny nz [iters [outputMatrix?]]')
         call MPI_Abort(MPI_COMM_WORLD, 1, ierr)
      endif

 355  format(I10)
      call getarg(1, arg)
      read(arg, 355) nx
      call getarg(2, arg)
      read(arg, 355) ny
      call getarg(3, arg)
      read(arg, 355) nz
      niter = 0
      outputMatrix = 0
      if (argc .ge. 4) then
         call getarg(4, arg)
         read(arg, 355) niter
      endif
      if (argc .ge. 5) then
         call getarg(5, arg)
         read(arg, 355) outputMatrix
      endif

      if (me .eq. 0) then
         print *, 'argc=', argc
         print *, 'nx=', nx
         print *, 'ny=', ny
         print *, 'nz=', nz
         print *, 'np=', np
         print *, 'niter=', niter
         print *, 'outputMatrix=', outputMatrix
      endif


      if (.not. ((nx .gt. 0) .and. (ny .gt. 0) .and. (nz .gt. 0) 
     >     .and. (mod(ny, np) .eq. 0) .and. (mod(nz, np) .eq. 0) )) then
         write(*, 239)
 239     format('wrong configuration nx, ny, nz, np!')
         call MPI_Abort(MPI_COMM_WORLD, 1, ierr)
      endif

      write(fname, 240) me
 240  format('out.ft', I0, '.txt')
      fout = 22
      open(unit=fout, file=fname, action='write', status='replace')

      return
      end

      

      subroutine transpose_xy_z(xin, xout, timers)

      implicit none
      include 'global.h'
      integer n1, n2
      double precision xin(ntdivnp), xout(ntdivnp)
      integer timers(:)

      call timer_start(timers(1))

      n1 = nx * ny
      n2 = nz / np

      if (.FALSE. .and. outputMatrix .gt. 0) then
          write(fout, 3000) ntdivnp
3000      format('ntdivnp=', I0, ' initial xin:')
          call output_matrix(nx, ny, nz/np, xin)
      endif

      call timer_start(timers(2))
      call transpose2_local(n1, n2, xin, xout)
      call timer_stop(timers(2))
      if (.FALSE. .and. outputMatrix .gt. 0) then
          write(fout, 3005)
3005      format('after local xout (n2, n1):')
          call output_matrix(n2, n1, 1, xout)
          write(fout, 3010)
3010      format('after local xout (nz/np, nx, ny):')
          call output_matrix(nz/np, nx, ny, xout)
      endif

      call timer_start(timers(3))
      call transpose2_global(xout, xin)
      call timer_stop(timers(3))
      if (.FALSE. .and. outputMatrix .gt. 0) then
          write(fout, 3020)
3020      format('after global xin:')
          call output_matrix(nz/np, nx, ny, xin)
      endif

      call timer_start(timers(4))
      call transpose2_finish(n1, n2, xin, xout)
      call timer_stop(timers(4))

      call timer_stop(timers(1))
      return
      end



      subroutine transpose2_local(n1, n2, xin, xout)

      implicit none
      include 'mpinpb.h'
      include 'global.h'
      integer n1, n2
      double precision xin(n1, n2), xout(n2, n1)
      
      double precision z(transblockpad, transblock)

      integer i, j, ii, jj

c---------------------------------------------------------------------
c If possible, block the transpose for cache memory systems. 
c How much does this help? Example: R8000 Power Challenge (90 MHz)
c Blocked version decreases time spend in this routine 
c from 14 seconds to 5.2 seconds on 8 nodes class A.
c---------------------------------------------------------------------
      if (.FALSE. .and. outputMatrix .gt. 0) then
          write(fout, 7010) ntdivnp
7010      format('ntdivnp=', I0, ' initial xin (nx, ny, nz/np):')
          call output_matrix(nx, ny, nz/np, xin)
          write(fout, 7020) n1, n2
7020      format('n1=', I0, ' n2=', I0, ' initial xin (n1, n2):')
          call output_matrix(n1, n2, 1, xin)
      endif

      if (.TRUE. .or. (n1 .lt. transblock .or. n2 .lt. transblock)) then
         if (n1 .ge. n2) then 
            do j = 1, n2
               do i = 1, n1
                  xout(j, i) = xin(i, j)
               enddo
            enddo
         else
            do i = 1, n1
               do j = 1, n2
                  xout(j, i) = xin(i, j)
               enddo
            enddo
         endif
      else
         do j = 0, n2-1, transblock
            do i = 0, n1-1, transblock
               
c---------------------------------------------------------------------
c Note: compiler should be able to take j+jj out of inner loop
c---------------------------------------------------------------------
               do jj = 1, transblock
                  do ii = 1, transblock
                     z(jj,ii) = xin(i+ii, j+jj)
                  enddo
               enddo
               
               do ii = 1, transblock
                  do jj = 1, transblock
                     xout(j+jj, i+ii) = z(jj,ii)
                  enddo
               enddo
               
            enddo
         enddo
      endif

      if (.FALSE. .and. outputMatrix .gt. 0) then
          write(fout, 7030) ntdivnp
7030      format('ntdivnp=', I0, ' after local xout (nx, ny, nz/np):')
          call output_matrix(nz/np, nx, ny, xout)
          write(fout, 7040) n1, n2
7040      format('n1=', I0, ' n2=', I0, ' after local xout (n2, n1):')
          call output_matrix(n2, n1, 1, xout)
      endif


      return
      end


c---------------------------------------------------------------------
c---------------------------------------------------------------------

      subroutine transpose2_global(xin, xout)

c---------------------------------------------------------------------
c---------------------------------------------------------------------

      implicit none
      include 'global.h'
      include 'mpinpb.h'
      double precision xin(ntdivnp)
      double precision xout(ntdivnp) 
      integer ierr

      call mpi_alltoall(xin, ntdivnp/np, dc_type,
     >                  xout, ntdivnp/np, dc_type,
     >                  MPI_COMM_WORLD, ierr)

      return
      end



c---------------------------------------------------------------------
c---------------------------------------------------------------------

      subroutine transpose2_finish(n1, n2, xin, xout)

c---------------------------------------------------------------------
c---------------------------------------------------------------------

      implicit none
      include 'global.h'
      integer n1, n2, ioff
      double precision xin(n2, n1/np, 0:np-1), xout(n2*np, n1/np)
      
      integer i, j, p

      do p = 0, np-1
         ioff = p*n2
         do j = 1, n1/np
            do i = 1, n2
               xout(i+ioff, j) = xin(i, j, p)
            enddo
         enddo
      enddo

      return
      end

