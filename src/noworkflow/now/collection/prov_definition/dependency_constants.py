# Copyright (c) 2019 Universidade Federal Fluminense (UFF)
# Copyright (c) 2019 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define dependency constants"""

ARGUMENT = "argument"
#  stmt.process_default
#  expr._call_arg
#  expr._call_keyword
#  expr.process_call_arg
#  expr.process_call_keyword
ASSIGN = "assign"
#  stmt.visit_assign
#  stmt.visit_annassign
BASE = "base"
#  stmt.visit_ClassDef
CONDITION = "condition"
#  stmt.visit_While
#  stmt.visit_If
#  expr.visit_IfExp
#  expr.visit_generator
DECORATE = "decorate"
#  stmt.visit_FunctionDef
#  stmt.visit_ClassDef
DECORATOR = "decorator"
#  stmt.process_decorator
DEPENDENCY = "dependency"
#  stmt.visit_With
#  stmt.process_withitem
WITHITEM = "withitem"
#  stmt.visit_ClassDef
#  stmt.visit_Print
#  stmt.visit_For
#  stmt.visit_Exec
#  stmt.capture
#  expr.RewriteDependencies.__init__
#  expr.visit_generator
#  expr.visit_Attribute
#  expr.visit_Subscript
FUNC = "func"
#  expr.visit_Call
ITEM = "item"
#  expr._itemize
#  expr.yield
KEY = "key"
#  expr._dict_itemize
SLICE = "slice"
#  expr.visit_Subscript
USE = "use"
#  stmt.process_decorator
#  stmt.visit_Return
#  expr.visit_BoolOp
#  expr.visit_BinOp
#  expr.visit_UnaryOp
#  expr.visit_Lambda
#  expr.visit_IfExp
#  expr.visit_Compare
#  expr.visit_FormattedValue
#  expr.visit_JoinedStr
#  expr.visit_Slice
#  expr.visit_ExtSlice
VALUE = "value"
#  expr._dict_itemize
#  expr.visit_Attribute
#  expr.visit_Subscript


# stmt.visit_augassign:
#   add_assign
#   mult_assign
#   div_assign
#   floordiv_assign
#   pow_assign
#   sub_assign
#   mod_assign
#   matmult_assign
#   ...