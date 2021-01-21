# Copyright (c) 2019 Universidade Federal Fluminense (UFF)
# Copyright (c) 2019 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define code component constants"""


# Code Component

ANNOTATION = "annotation"
#  stmt.visit_annassign
ARGUMENT = "argument"
#  expr._call_arg
#  expr._call_keyword
ARGUMENTS = "arguments"
#  stmt.process_parameters
ASSERT = "assert"
#  stmt.visit_Assert
ASSIGN = "assign"
#  stmt.visit_assign
ANN_ASSIGN = "ann_assign"
#  stmt.visit_annassign
ANN_TARGET = "ann_target"
#  stmt.visit_annassign
ASYNC_FOR = "async_for"
#  stmt.visit_AsyncFor
ASYNC_WITH = "async_with"
#  stmt.visit_AsyncWith
AUG_ASSIGN = "aug_assign"
#  stmt.visit_augassign
AWAIT = "await"
#  expr.visit_Await
ATTRIBUTE = "attribute"
#  expr.visit_Attribute 
BREAK = "break"
#  stmt.visit_Break
CALL = "call"
#  stmt.visit_Exec
#  expr.visit_Call
CLASS_DEF = "class_def"
#  stmt.visit_ClassDef
CONTINUE = "continue"
#  stmt.visit_Continue
CONVERSION = "conversion"
#  expr.visit_FormattedValue
COMPREHENSION = "comprehension"
#  expr.visit_generator
DECORATOR = "decorator"
#  stmt.process_decorator
DEFAULT = "default"
#  stmt.process_default
DELETE = "delete"
#  stmt.visit_Delete
DICT = "dict"
#  expr.visit_Dict
DICTCOMP = "dictcomp"
#  expr.visit_DictComp
EXCEPTION = "exception"
#  stmt.visit_exchandler
EXPR = "expr"
#  stmt.visit_Expr
EXTSLICE = "extslice"
#  expr.visit_ExtSlice
FOR = "for"
#  stmt.visit_For
FSTRING = "fstring"
#  expr.visit_JoinedStr
FUNC = "func"
#  expr.visit_Call
FUNCTION_DEF = "function_def"
#  stmt.visit_FunctionDef
FUTURE_IMPORT = "future_import"
#  stmt.process_script
F_VALUE = "fvalue"
#  expr.visit_FormattedValue
GLOBAL = "global"
#  stmt.visit_Global
IDENTIFIER = "identifier"
#  stmt.visit_FunctionDef
#  stmt.visit_ClassDef
IF = "if"
#  stmt.visit_If
IFEXP = "ifexp"
#  expr.visit_IfExp
INDEX = "index"
#  expr.visit_Index
IMPORT = "import"
#  stmt.visit_Import
IMPORT_FROM = "import_from"
#  stmt.visit_ImportFrom
ITEM = "item"
#  expr.visit_Yield
KEY_VALUE = "key_value"
#  expr._dict_itemize
LAMBDA_DEF = "lambda_def"
#  expr.visit_Lambda
LITERAL = "literal"
#  expr.visit_JoinedStr
#  expr.visit_Ellipsis
#  expr.visit_literal
NAME = "name"
#  expr.visit_Name
NONLOCAL = "nonlocal"
#  stmt.visit_Nonlocal
PASS = "pass"
#  stmt.visit_Pass
PARAM = "param"
#  stmt.process_arg
PRINT = "print"
#  stmt.visit_Print
RAISE = "raise"
#  stmt.visit_Raise
RETURN = "return"
#  stmt.visit_Return
SLICE = "slice"
#  expr.visit_Slice
STARRED = "starred"
#  expr.visit_Starred
SUBSCRIPT = "subscript"
#  expr.visit_Subscript
SYNTAX = "syntax"
#  stmt.create_code_component
TRY = "try"
#  stmt.visit_Try
TRY_EXCEPT = "try_except"
#  stmt.visit_TryExcept
TRY_FINALLY = "try_finally"
#  stmt.visit_TryFinally
WHILE = "while"
#  stmt.visit_While
WITH = "with"
WITHITEM = "withitem"
#  stmt.visit_With
YIELD = "yield"
#  expr.visit_Yield
YIELD_FROM = "yield_from"
#  expr.visit_YieldFrom

# expr.visit_BoolOp:
#  and, or

# expr.visit_BinOp:
#  add, sub, div, floordiv, mult, matmul, ...

# expr.visit_UnaryOp:
#  inv

# expr.visit_ListComp:
#  listcomp, setcomp, dictcomp

# expr.visit_Compare:
#  eq, gt, lt, ge, le

# Composition

S_ANNOTATION = "annotation"
M_ARGS = "*args"
#  stmt.process_parameters
#  expr.visit_Call
S_ARGS = "args"
#  stmt.visit_FunctionDef
#  stmt.visit_ClassDef
#  stmt.visit_Lambda
S_ATTR = "attr"
#  expr.visit_Attribute
M_BASES = "*bases"
#  stmt.visit_ClassDef
M_BODY = "*body"
#  stmt.process_script
#  stmt.process_body
S_BODY = "body"
#  expr.visit_Lambda
#  expr.visit_IfExp
M_COMPARATORS = "*comparators"
#  expr.visit_Compare
M_DECORATOR_LIST = "*decorator_list"
#  stmt.visit_FunctionDef
#  stmt.visit_ClassDef
M_DEFAULTS = "*defaults"
#  stmt.process_parameters
S_DEST = "dest"
#  stmt.visit_Print
M_DIMS = "*dims"
#  expr.visit_ExtSlice
S_ELT = "elt"
#  expr.visit_ListComp
M_ELTS = "*elts"
#  expr.visit_List
M_FINALBODY = "*finalbody"
#  stmt.visit_Try
#  stmt.visit_TryFinally
S_FORMAT_SPEC = "format_spec"
#  expr.visit_FormattedValue
S_FUNC = "func"
#  expr.visit_Call
M_GENERATORS = "*generators"
#  expr.visit_ListComp
#  expr.visit_DictComp
M_HANDLERS = "*handlers"
#  stmt.visit_Try
#  stmt.visit_TryExcept
S_ITER = "iter"
#  stmt.visit_For
#  expr.visit_generator
M_IFS = "*ifs"
#  expr.visit_generator
S_ITEM = "item"
#  expr._itemize
S_KEY = "key"
#  expr._dict_itemize
M_KEYWORDS = "*keywords"
#  stmt.visit_ClassDef
#  expr.visit_Call
S_KWARG = "kwarg"
#  stmt.process_parameters
S_KWARGS = "kwargs"
#  expr.visit_Call
M_KWONLYARGS = "*kwonlyargs"
#  stmt.process_parameters
M_KW_DEFAULTS = "*kw_defaults"
#  stmt.process_parameters
S_KEY_VALUE = "key_value"
#  expr.visit_Dict
#  expr.visit_DictComp
S_LEFT = "left"
#  expr.visit_BinOp
#  expr.visit_Compare
S_LOCALS = "locals"
#  stmt.visit_Exect
S_LOWER = "lower"
#  expr.visit_Slice
S_NAME_NODE = "name_node"
#  stmt.visit_FunctionDef
#  stmt.visit_ClassDef
S_NL = "nl"
#  stmt.visit_Print
M_OP_POS = "*op_pos"
#  stmt.create_code_component
S_OPERAND = "operand"
#  expr.visit_UnaryOp
M_ORELSE = "*orelse"
#  stmt.visit_For
#  stmt.visit_While
#  stmt.visit_If
#  stmt.visit_Try
S_ORELSE = "orelse"
#  expr.visit_IfExp
S_RIGHT = "right"
#  expr.visit_BinOp
S_SIMPLE = "simple"
#  stmt.visit_annassign
S_SLICE = "slice"
#  expr.visit_Subscript
S_STARARGS = "starargs"
#  expr.visit_starargs
S_STEP = "step"
#  expr.visit_Slice
S_TARGET = "target"
#  stmt.visit_augassign
#  stmt.visit_annassign
#  stmt.visit_For
#  expr.visit_generator
M_TARGETS = "*targets"
#  stmt.visit_assign
S_TEST = "test"
#  stmt.visit_While
#  stmt.visit_If
#  expr.visit_IfExp
S_UPPER = "upper"
#  expr.visit_Slice
S_VALUE = "value"
#  stmt.visit_Return
#  stmt.visit_assign
#  stmt.visit_augassign
#  stmt.visit_annassign
#  stmt.visit_Expr
#  expr._dict_itemize
#  expr.visit_Yield
#  expr.visit_Repr
#  expr.visit_FormattedValue
#  expr.visit_Attribute
#  expr.visit_Subscript
#  expr.visit_Starred
#  expr.visit_Index
M_VALUES = "*values"
#  stmt.visit_Print
#  expr.visit_BoolOp
#  expr.visit_JoinedStr
S_VARARG = "vararg"
#  stmt.process_parameters
M_ITEMS = "*items"
#  stmt.visit_WITH


