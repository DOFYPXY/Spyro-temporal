var {
    int p;
    Trace tr;
}

relation {
    prog(p, tr);
}

generator {
    boolean AP -> Now(PT);
    BoolArray PT -> Globally(PNT);
    BoolArray PNT -> map((x)->(x == p), tr) | map((x)->(x == 0), tr) | map((x)->(x == 1), tr) ;
}


example {
    int -> ??(1);
    boolean -> ??(1);
    Trace -> randomTrace();
}

struct BoolArray{
    boolean[8] elements;
}

struct Event{
    int x;
}

struct Trace{
    Event[8] events;
}

generator void randomTrace(ref Trace tr){
    tr = new Trace();
    tr.events[0] = new Event(x = ??(1));
    tr.events[1] = new Event(x = ??(1));
    tr.events[2] = new Event(x = ??(1));
    tr.events[3] = new Event(x = ??(1));
    tr.events[4] = new Event(x = ??(1));
    tr.events[5] = new Event(x = ??(1));
    tr.events[6] = new Event(x = ??(1));
    tr.events[7] = new Event(x = ??(1));
}

void Eventually(BoolArray seq, ref BoolArray ret) {
    boolean[8] elements;
    elements[7] = seq.elements[7];
    for(int i=6;i>=0;i--) {
        elements[i] = elements[i+1] || seq.elements[i];
    }
    ret = new BoolArray(elements = elements);
}

void Globally(BoolArray seq, ref BoolArray ret) {
    boolean[8] elements;
    elements[7] = seq.elements[7];
    for(int i=6;i>=0;i--) {
        elements[i] = elements[i+1] && seq.elements[i];
    }
    ret = new BoolArray(elements = elements);
}

void Now(BoolArray seq, ref boolean ret)
{
    ret = seq.elements[0];
}

void map(fun f, Trace tr, ref BoolArray ret) {
   boolean[8] elements;
   for(int i=0;i<8;i++) 
        elements[i] = f(tr.events[i].x);   
    ret = new BoolArray(elements = elements);   
}

void prog(int p, ref Trace tr) {
    for(int i=0;i<8;i++)
        tr.events[i].x = p;
}