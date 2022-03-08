from util import *

def replace_last_argument(text, var):
    start = text.rfind(',')
    end = text.rfind(')')

    return text[:start] + ', out' + text[end:]

class OutputParser:
    def __init__(self, text):
        self._text = text.decode('utf-8')

    def _get_function_code_lines(self, function_name):
        lines = self._text.splitlines()
        
        target = 'void ' + function_name + ' ('
        start = find_linenum_starts_with(lines, target)
        end = find_linenum_starts_with(lines, '}', start)

        return lines[start+2:end]

    def parse_positive_example(self):       
        soundness_code_lines = self._get_function_code_lines('soundness')
        soundness_code_lines = ['\t' + line.strip() for line in soundness_code_lines]

        property_call = soundness_code_lines[-2].replace('obtained_property', 'property')
        property_call = replace_last_argument(property_call, 'out')

        positive_example_code = '\n'.join(soundness_code_lines[:-3])
        positive_example_code += '\n\tboolean out;'
        positive_example_code += '\n' + property_call
        positive_example_code += '\n\tassert out;' 

        return positive_example_code

    def parse_negative_example(self):
        precision_code_lines = self._get_function_code_lines('precision')
        precision_code_lines = ['\t' + line.strip() for line in precision_code_lines]

        property_call = replace_last_argument(precision_code_lines[-2], 'out')

        negative_example_code = '\n'.join(precision_code_lines[:-9])
        negative_example_code += '\n\tboolean out;'
        negative_example_code += '\n' + property_call
        negative_example_code += '\n\tassert !out;'

        return negative_example_code

    def parse_maxsat(self, neg_examples):
        maxsat_code_lines = self._get_function_code_lines('maxsat') 
        maxsat_code = '\n'.join(maxsat_code_lines)

        used_neg_examples = []
        discarded_examples = []
        for i, e in enumerate(neg_examples):
            if 'negative_example_{}'.format(i) in maxsat_code:
                used_neg_examples.append(e)
            else:
                discarded_examples.append(e)
        
        return used_neg_examples, discarded_examples

    def parse_property(self):
        property_code_lines = self._get_function_code_lines('property')
        property_code_lines = ['\t' + line.strip() for line in property_code_lines]

        property_code = '\n'.join(property_code_lines)

        return property_code.strip()