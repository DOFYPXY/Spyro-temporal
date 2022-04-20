import os
import functools
from template_parser import TemplateParser
from util import *

class InputGenerator:
    # To-Do: Generate codes from variables and relations

    def __init__(self, code):
        # Input code
        self.__template = TemplateParser(code)
        self.__fresh_num = 0
        self.__num_atom = 1

    def set_num_atom(self, num_atom):
        self.__num_atom = num_atom

    def num_atom(self):
        return self.__num_atom

    def __soundness_code(self):
        code = 'harness void soundness() {\n'
        code += self.__template.get_variables_with_hole() + '\n\n'
        code += self.__template.get_relations() + '\n\n'
        
        code += '\tboolean out;\n'
        code += '\tobtained_property(' + self.__template.get_arguments_call() + ',out);\n'
        code += '\tassert !out;\n'
        
        code += '}\n\n'

        return code

    def __precision_code(self):
        code = 'harness void precision() {\n'
        code += self.__template.get_variables_with_hole() + '\n\n'
        
        arguments = self.__template.get_arguments_call()

        code += '\tboolean out_1;\n'
        code += '\tobtained_property(' + arguments + ',out_1);\n'
        code += '\tassert out_1;\n\n'

        code += '\tboolean out_2;\n'
        code += '\tproperty_conj(' + arguments + ',out_2);\n'
        code += '\tassert out_2;\n\n'

        code += '\tboolean out_3;\n'
        code += '\tproperty(' + arguments + ',out_3);\n'
        code += '\tassert !out_3;\n'
        code += '}\n\n'

        return code

    def __change_behavior_code(self):
        code = 'harness void change_behavior() {\n'
        code += self.__template.get_variables_with_hole() + '\n\n'
        
        arguments = self.__template.get_arguments_call()

        code += '\tboolean out_1;\n'
        code += '\tproperty_conj(' + arguments + ',out_1);\n'
        code += '\tassert out_1;\n\n'

        code += '\tboolean out_2;\n'
        code += '\tobtained_property(' + arguments + ',out_2);\n'
        code += '\tassert !out_2;\n'
        
        code += '}\n\n'

        return code

    def __property_code(self):
        property_gen_symbol = self.__template.get_generator_rules()[0][1]
        arg_call = self.__template.get_arguments_call()
        arg_defn = self.__template.get_arguments_defn()

        atom_gen = f'{property_gen_symbol}_gen({arg_call})'
        property_gen = ' || '.join([f'atom_{i}' for i in range(self.__num_atom)])

        code = self.__generators() + '\n\n'
        code += f'generator boolean property_gen({arg_defn}) {{\n'
        for i in range(self.__num_atom):
            code += f'\tboolean atom_{i} = {atom_gen};\n'
        code += f'\treturn {property_gen};\n'
        code += '}\n\n'

        code += f'void property({arg_defn},ref boolean out) {{\n'
        code += f'\tout = property_gen({arg_call});\n'
        code += '}\n\n'

        return code

    def __obtained_property_code(self, phi):
        code = 'void obtained_property('
        code += self.__template.get_arguments_defn()
        code += ',ref boolean out) {\n'
        code += '\t' + phi + '\n'
        code += '}\n\n'

        return code

    def __prev_property_code(self, i, phi):
        code = f'void prev_property_{i}('
        code += self.__template.get_arguments_defn()
        code += ',ref boolean out) {\n'
        code += '\t' + phi + '\n'
        code += '}\n\n'

        return code

    def __property_conj_code(self, phi_list):
        code = ''

        for i, phi in enumerate(phi_list):
            code += self.__prev_property_code(i, phi) + '\n\n'      

        code += 'void property_conj('
        code += self.__template.get_arguments_defn()
        code += ',ref boolean out) {\n'

        for i in range(len(phi_list)):
            code += f'\tboolean out_{i};\n'
            code += f'\tprev_property_{i}(' 
            code += self.__template.get_arguments_call() 
            code += f',out_{i});\n\n' 

        if len(phi_list) == 0:
            code += '\tout = true;\n'
        else:
            code += '\tout = ' + ' && '.join([f'out_{i}' for i in range(len(phi_list))]) + ';\n'
        code += '}\n\n'

        return code

    def __examples(self, pos_examples, neg_examples, check_maxsat = False):
        code = ''

        for i, pos_example in enumerate(pos_examples):
            code += '\n'
            code += 'harness void positive_example_{} ()'.format(i)
            code += ' {\n' + pos_example + '\n}\n\n'

        for i, neg_example in enumerate(neg_examples):
            code += '\n'
            if check_maxsat:
                code += 'void negative_example_{} ()'.format(i)
            else:   
                code += 'harness void negative_example_{} ()'.format(i)
            code += ' {\n' + neg_example + '\n}\n\n'      

        return code       

    def __maxsat(self, num_neg_examples):
        code = 'harness void maxsat() {\n'
        code += f'\tint cnt = {num_neg_examples};\n'

        for i in range(num_neg_examples):
            code += f'\tif (??) {{ cnt -= 1; negative_example_{i}(); }}\n'

        code += '\tminimize(cnt);\n'
        code += '}\n\n'

        return code

    def __model_check(self, neg_example):
        code = 'harness void model_check() {\n'

        neg_example = '\n'.join(neg_example.splitlines()[:-1])
        code += neg_example.replace('property', 'property_conj')
        code += '\tassert out;\n'

        code += '\tboolean trivial_target = ??;\n'
        code += '\tassert trivial_target;\n'

        code += '}\n\n'

        return code

    def __count_generator_calls(self, cxt, expr):
        if expr[0] == 'BINOP':
            d1 = self.__count_generator_calls(cxt, expr[2])
            d2 = self.__count_generator_calls(cxt, expr[3])
            return sum_dict(d1, d2)
        elif expr[0] == 'UNARY':
            return self.__count_generator_calls(cxt, expr[2])
        elif expr[0] == 'INT' or expr[0] == 'HOLE':
            return dict()
        elif expr[0] == 'VAR':
            return {expr[1] : 1} if expr[1] in cxt else dict()
        elif expr[0] == 'FCALL':
            dicts = [self.__count_generator_calls(cxt, e) for e in expr[2]]
            return functools.reduce(sum_dict, dicts)
        else:
            raise Exception(f'Unhandled case: {expr[0]}')

    def __subcall_gen(self, num_calls_prev, num_calls):
        cxt = self.__template.get_context()
        arg_call = self.__template.get_arguments_call()

        code = ''
        for symbol, n in num_calls.items():
            if symbol not in num_calls_prev:
                for i in range(n):
                    code += f'\t{cxt[symbol]} var_{symbol}_{i} = {symbol}_gen({arg_call});\n'
            elif num_calls_prev[symbol] < n:
                for i in range(num_calls_prev[symbol], n):
                    code += f'\t{cxt[symbol]} var_{symbol}_{i} = {symbol}_gen({arg_call});\n'

        return code + '\n'

    def __fresh_variable(self):
        n = self.__fresh_num
        self.__fresh_num += 1

        return f'var_{n}'

    def __expr_to_code(self, cxt, expr):
        if expr[0] == 'BINOP':
            cxt1, code1, out1 = self.__expr_to_code(cxt, expr[2])
            cxt2, code2, out2 = self.__expr_to_code(cxt1, expr[3])
            return (cxt2, code1 + code2, f'{out1} {expr[1]} {out2}')
        elif expr[0] == 'UNARY':
            cxt, code, out = self.__expr_to_code(cxt, expr[2])
            return (cxt, code, f'{expr[1]} {out}')
        elif expr[0] == 'INT':
            return (cxt, '', expr[1])
        elif expr[0] == 'VAR':
            symbol = expr[1]
            if symbol in cxt:
                count = cxt[symbol]
                cxt[symbol] += 1
                return (cxt, '', f'var_{symbol}_{count}')
            else:
                return (cxt, '', symbol)
        elif expr[0] == 'HOLE':
            code = '??' if expr[1] == 0 else f'??({expr[1]})'
            return (cxt, '', code)
        elif expr[0] == 'FCALL':
            code = ''
            args = []
            for e in expr[2]:
                cxt, code_sub, out_sub = self.__expr_to_code(cxt, e)
                code += code_sub
                args.append(out_sub)

            args_call = ','.join(args)
            fresh_var = self.__fresh_variable()
            code += f'\t\tboolean {fresh_var};\n'
            code += f'\t\t{expr[1]}({args_call},{fresh_var});\n'
            return (cxt, code, fresh_var)
        else:
            raise Exception(f'Unhandled case: {expr}')

    def __rule_to_code(self, rule):
        typ = rule[0]
        symbol = rule[1]
        exprlist = rule[2]

        cxt = self.__template.get_context()
        dicts = [self.__count_generator_calls(cxt, e) for e in exprlist]
        num_calls = functools.reduce(max_dict, dicts)
        num_calls_prev = dict()

        arg_defn = self.__template.get_arguments_defn()

        code = f'generator {typ} {symbol}_gen({arg_defn}) {{\n'
        code += '\tint t = ??;\n'
        
        for n, e in enumerate(exprlist):
            num_calls = self.__count_generator_calls(cxt, e)
            code += self.__subcall_gen(num_calls_prev, num_calls)
            num_calls_prev = max_dict(num_calls_prev, num_calls)

            cxt_init = {k:0 for k in cxt.keys()}
            _, e_code, e_out = self.__expr_to_code(cxt_init, e)

            code += f'\tif (t == {n}) {{\n'
            code += e_code
            code += f'\t\treturn {e_out};\n'
            code += '\t}\n'

        code += '}\n'

        return code

    def __struct_generator(self, st):
        st_name = st[0]
        elements = st[1]
        var_name = 'tmp'

        code = f'generator {st_name} {st_name}_gen() {{\n'
        code += '\tint t = ??;\n'

        code += f'\tif (t == 0) {{ return null; }}\n'
        code += '\tif (t == 1) {\n'
        code += f'\t\t{st_name} {var_name} = new {st_name}();\n'

        for n, (typ, sym) in enumerate(elements):
            code += f'\t\t{var_name}.{sym} = {typ}_gen();\n'

        code += f'\t\treturn {var_name};\n'
        code += '\t}\n'
        code += '}\n'

        return code

    def __generators(self):
        rules = self.__template.get_generator_rules()

        return '\n'.join([self.__rule_to_code(rule) for rule in rules]) + '\n'

    def __example_rule_to_code(self, rule):
        typ = rule[0]
        exprlist = rule[1]

        code = f'generator {typ} {typ}_gen() {{\n'
        code += '\tint t = ??;\n'
        
        for n, e in enumerate(exprlist):
            cxt_init = dict()
            _, e_code, e_out = self.__expr_to_code(cxt_init, e)

            code += f'\tif (t == {n}) {{\n'
            code += e_code
            code += f'\t\treturn {e_out};\n'
            code += '\t}\n'

        code += '}\n'

        return code    

    def __example_generators(self):
        rules = self.__template.get_example_rules()
        structs = self.__template.get_structs()

        code = '\n'.join([self.__example_rule_to_code(rule) for rule in rules]) + '\n'
        code += '\n'.join([self.__struct_generator(st) for st in structs]) + '\n'

        return code

    def generate_synthesis_input(self, phi, pos_examples, neg_examples):
        code = self.__template.get_implementation()
        code += self.__examples(pos_examples, neg_examples)
        code += self.__property_code()

        return code

    def generate_soundness_input(self, phi, pos_examples, neg_examples):
        code = self.__template.get_implementation()
        code += self.__obtained_property_code(phi)
        code += self.__example_generators()
        code += self.__soundness_code()

        return code

    def generate_precision_input(self, phi, phi_list, pos_examples, neg_examples):
        code = self.__template.get_implementation()
        code += self.__examples(pos_examples, neg_examples)
        code += self.__property_code()
        code += self.__obtained_property_code(phi)
        code += self.__property_conj_code(phi_list)
        code += self.__example_generators()
        code += self.__precision_code()

        return code

    def generate_maxsat_input(self, pos_examples, neg_examples):
        code = self.__template.get_implementation()
        code += self.__examples(pos_examples, neg_examples, True)
        code += self.__example_generators()
        code += self.__property_code()
        code += self.__maxsat(len(neg_examples))

        return code

    def generate_change_behavior_input(self, phi, phi_list):
        code = self.__template.get_implementation()
        code += self.__property_conj_code(phi_list)
        code += self.__obtained_property_code(phi)
        code += self.__example_generators()
        code += self.__change_behavior_code()

        return code

    def generate_model_check_input(self, phi_list, neg_example):
        code = self.__template.get_implementation()
        code += self.__property_conj_code(phi_list)
        code += self.__example_generators()
        code += self.__model_check(neg_example)

        return code