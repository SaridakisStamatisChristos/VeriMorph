from typing import List
from .interpreter_secure import Program, WhileStmt, IfStmt, FuncDef

def analyze_ast(program: Program) -> List[str]:
    """Very small static analysis: flag unbounded while loops (no END is impossible here),
    suspicious deep nesting (toy heuristic), and excessive function count."""
    warns: List[str] = []

    # Heuristic: nested while > 3
    def max_while_depth(stmts, depth=0):
        d = depth
        for s in stmts:
            if isinstance(s, WhileStmt):
                d = max(d, max_while_depth(s.body, depth+1))
            elif isinstance(s, IfStmt):
                d = max(d, max_while_depth(s.then_body, depth),
                        max_while_depth(s.else_body or [], depth))
        return d

    total_depth = 0
    for f in program.functions.values():
        total_depth = max(total_depth, max_while_depth(f.body, 0))

    if total_depth > 3:
        warns.append(f"Deep while nesting detected: depth={total_depth}")

    if len(program.functions) > 100:
        warns.append("Large number of functions may indicate code bomb")

    return warns
