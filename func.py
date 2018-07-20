import ast
import inspect
import re
import types

from ir import Function
from ir import Script

from utils import *


def recompile(fn, old_func):
    source = ''.join(fn.lines)

    print(source)
    print("\n")

    module = ast.parse(source)
    func = module.body[0]
    module_code = compile(source, '<string>', 'exec')

    func_code = None
    for const in module_code.co_consts:
        if isinstance(const, types.CodeType):
            func_code = const

    new_fn = types.FunctionType(
        func_code, old_func.__globals__.copy(), name=fn.name)
    return new_fn


def set_function_meta(fn):
    is_in_proto = False
    fn.indent = get_indentation(fn.lines[0])
    for lineno, line in enumerate(fn.lines):
        if line.lstrip().startswith("def "):
            if not is_in_proto:
                is_in_proto = True
            else:
                raise Exception(
                    """Invalid function definition. Multiple def key words in the
                    prototype for function {}""".format(fn.name))
            fn.proto_start = lineno

        if is_in_proto:
            if line.rstrip().endswith("\\"):
                continue
            elif line.rstrip().endswith(":"):
                fn.proto_end = lineno
                fn.body_start = lineno + 1
                is_in_proto = False
                fn.body_indent = get_indentation(fn.lines[fn.body_start])
                return
    if fn.proto_start == -1 or fn.proto_end == -1:
        raise Exception("Invalid function prototype for function {}".format(
            fn.name))


def normalize_fn_body(fn):
    # Match the tail end of prototype line. Prototype is of the form
    # 'def fn(..) [-> type]: <body | \n>' which may be
    # spread across multiple lines with '\' continuation
    prototype_regex = re.compile("(.*\).*:)(.*)", re.DOTALL)
    proto_end = -1
    first_line_of_body = []

    is_in_proto = False
    for lineno, line in enumerate(fn.lines):
        # This is the start of the function prototype
        if line != None and line.lstrip().startswith("def "):
            is_in_proto = True

        # We set 'is_in_proto' in above conditional and do the prototype
        # termination logic given below separately since the prototype may span
        # multiple lines. So it may be several lines later than when we found
        # the 'def ' in the conditional above
        if is_in_proto:
            match = re.search(prototype_regex, line)
            if match:
                proto_end = lineno
                prototype = match.group(1)
                maybe_body = match.group(2)

                if maybe_body.isspace():
                    # Just a plain old function with a new line after ':'. We
                    # are good. Nothing to normalize.
                    return

                # We have function body tacked on to the end of function
                # prototype!!! Separate it and make it a line of its own
                if maybe_body.strip().endswith('\\'):
                    # Replace the current prototype
                    fn.lines[lineno] = prototype + '\n'

                    # Follow until the end of the line and add the accumulated
                    # buffer as the first line of the body
                    first_line_of_body = [maybe_body]
                else:
                    # Replace the current prototype
                    fn.lines[lineno] = prototype + '\n'
                    # Add the newly separated body
                    fn_indent = get_indentation(fn.lines[0])
                    fn.lines.insert(lineno + 1,
                                    gen_spaces(fn_indent + 4) + maybe_body)
                    return
            else:
                # Prototype is split in to multiple lines after ':'
                # Whatever after ':' belongs to the first line of the body.
                # Keep accumulating the first line of the body
                first_line_of_body.append(line)
                # Mark the line for deletion
                fn.lines[lineno] = None

                if not line.strip().endswith('\\'):
                    # We have arrived at the end of the first and last line
                    # of the function. Add the newly separated body after the
                    # prototype
                    fn_indent = get_indentation(fn.lines[0])
                    fn.lines.insert(
                        proto_end + 1,
                        gen_spaces(fn_indent + 4) +
                        ''.join(first_line_of_body))
                    is_in_proto = False

    fn.lines = [line for line in fn.lines if line != None]


def parse_fn(func):
    fn = Function()
    fn.name = func.__name__
    fn.lines = inspect.getsourcelines(func)[0]

    # Remove the annotation
    if fn.lines[0].strip().startswith("@"):
        del fn.lines[0]

    if len(fn.lines) <= 0:
        raise Exception("Empty function {}".format(fn.name))

    normalize_fn_body(fn)
    set_function_meta(fn)
    return fn