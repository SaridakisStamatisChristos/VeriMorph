#!/usr/bin/env python3
"""
Self-Modifying Mini-Language — Near NASA-Grade Build
Additions over hardened build:
- Deterministic mode via seeded RNG for EVOLVE (reproducibility)
- Audit logger (structured, append-only, in-memory with optional file dump)
- Resource contracts decorator (soft enforcement + post-checks)
- HMAC integrity for source (optional)
- Real-time hard timeout (Unix signal) wrapper class
- Static analysis hook integration point (pre-exec)
"""

import sys, re, socket, time, signal, hashlib, hmac, json, os, random
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Callable, Any

# Optional backends
_HAS_PSUTIL = False
try:
    import psutil  # type: ignore
    _HAS_PSUTIL = True
except Exception:
    pass

try:
    import resource  # Unix-only
    _HAS_RESOURCE = True
except Exception:
    _HAS_RESOURCE = False

try:
    import tracemalloc
    tracemalloc.start()
    _HAS_TRACEMALLOC = True
except Exception:
    _HAS_TRACEMALLOC = False

# ------------------ Config ------------------
MAX_STEPS_DEFAULT = 300_000
MAX_RECURSION_DEFAULT = 1_000
MAX_RECOMPILES_DEFAULT = 1_000
MAX_SOURCE_BYTES_DEFAULT = 256 * 1024
MAX_LINE_LEN = 8_192
MEMORY_PCT_LIMIT = 90.0
MEMORY_SOFT_LIMIT_MB = 1024

ALLOWED_HOSTS_DEFAULT = {"127.0.0.1", "localhost"}
ENABLE_NETWORK_DEFAULT = False
NETWORK_TIMEOUT_SEC = 3.0

EVOLVE_MAX_ITERS_HARD = 5_000
FORBIDDEN_PATTERNS = [r"\x00", r"[^\x09\x0A\x0D\x20-\x7E]"]

# ------------------ Lexer ------------------
TOKEN_SPEC = [
    ("NUMBER",   r'\d+'),
    ("ID",       r'[A-Za-z_][A-Za-z0-9_]*'),
    ("STRING",   r'"([^"\\]|\\.)*"'),
    ("OP",       r'==|!=|<=|>=|[+\-*/<>=]'),
    ("LPAREN",   r'\('),
    ("RPAREN",   r'\)'),
    ("LBRACE",   r'\{'),
    ("RBRACE",   r'\}'),
    ("COMMA",    r','),
    ("NEWLINE",  r'\n'),
    ("SEMI",     r';'),
    ("WS",       r'[ \t\r]+'),
]
KEYWORDS = {
    "FUNC", "IF", "THEN", "ELSE", "END", "WHILE", "DO", "RETURN",
    "PRINT", "PRINT_SOURCE", "MODIFY_LINE", "RECOMPILE_AND_GOTO",
    "EVOLVE", "OPTIMIZE", "SEND_SOURCE"
}
MASTER_RE = re.compile("|".join(f"(?P<{n}>{p})" for n,p in TOKEN_SPEC))

@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int

def tokenize(text: str) -> List['Token']:
    tokens = []
    line = 1; col = 1; pos = 0
    while pos < len(text):
        m = MASTER_RE.match(text, pos)
        if not m:
            raise SyntaxError(f"Unexpected character at line {line} col {col}: {text[pos]!r}")
        typ = m.lastgroup; val = m.group()
        if typ == "WS":
            pass
        elif typ == "NEWLINE":
            tokens.append(Token("NEWLINE", "\n", line, col))
            line += 1; col = 0
        elif typ == "ID" and val in KEYWORDS:
            tokens.append(Token(val, val, line, col))
        else:
            tokens.append(Token(typ, val, line, col))
        pos = m.end(); col += len(val)
    tokens.append(Token("EOF", "", line, col))
    return tokens

# ------------------ AST ------------------
@dataclass
class Program:
    functions: Dict[str, 'FuncDef']

@dataclass
class FuncDef:
    name: str
    params: List[str]
    body: List['Stmt']

class Stmt: pass

@dataclass
class Assign(Stmt):
    name: str
    expr: 'Expr'

@dataclass
class PrintStmt(Stmt):
    expr: 'Expr'

@dataclass
class PrintSourceStmt(Stmt):
    pass

@dataclass
class IfStmt(Stmt):
    cond: 'Expr'
    then_body: List['Stmt']
    else_body: Optional[List['Stmt']]

@dataclass
class WhileStmt(Stmt):
    cond: 'Expr'
    body: List['Stmt']

@dataclass
class CallStmt(Stmt):
    name: str
    args: List['Expr']

@dataclass
class ReturnStmt(Stmt):
    expr: Optional['Expr']

@dataclass
class ModifyLineStmt(Stmt):
    line_no: 'Expr'
    new_text: 'Expr'

@dataclass
class RecompileGotoStmt(Stmt):
    func_name: str

@dataclass
class OptimizeStmt(Stmt):
    pass

@dataclass
class EvolveStmt(Stmt):
    entry: str
    fitness_func: Optional[str]
    iterations: int

@dataclass
class SendSourceStmt(Stmt):
    target: 'Expr'

class Expr: pass

@dataclass
class Number(Expr):
    value: int

@dataclass
class Var(Expr):
    name: str

@dataclass
class StringLit(Expr):
    value: str

@dataclass
class BinOp(Expr):
    left: 'Expr'
    op: str
    right: 'Expr'

@dataclass
class CallExpr(Expr):
    name: str
    args: List['Expr']

# ------------------ Parser ------------------
class Parser:
    def __init__(self, tokens: List[Token]):
        self.toks = tokens; self.i = 0
    def cur(self) -> Token: return self.toks[self.i]
    def eat(self, typ: str) -> Token:
        if self.cur().type == typ:
            t = self.cur(); self.i += 1; return t
        raise SyntaxError(f"Expected {typ}, got {self.cur().type} at line {self.cur().line}")
    def maybe(self, typ: str) -> Optional[Token]:
        if self.cur().type == typ: return self.eat(typ)
        return None
    def parse(self) -> Program:
        funcs = {}
        while self.cur().type != "EOF":
            while self.maybe("NEWLINE"): pass
            if self.cur().type == "EOF": break
            f = self.parse_func()
            if f.name in funcs: raise SyntaxError(f"Duplicate function: {f.name}")
            funcs[f.name] = f
            while self.maybe("NEWLINE"): pass
        if "main" not in funcs: raise SyntaxError("Program must define FUNC main() { ... }")
        return Program(funcs)
    def parse_func(self) -> FuncDef:
        self.eat("FUNC"); name = self.eat("ID").value
        self.eat("LPAREN"); params = []
        if self.cur().type != "RPAREN":
            params.append(self.eat("ID").value)
            while self.maybe("COMMA"): params.append(self.eat("ID").value)
        self.eat("RPAREN"); self.eat("LBRACE")
        body = self.parse_block_until_rbrace(); self.eat("RBRACE")
        return FuncDef(name, params, body)
    def parse_block_until_rbrace(self) -> List[Stmt]:
        stmts = []
        while self.cur().type not in ("RBRACE","EOF"):
            while self.maybe("NEWLINE") or self.maybe("SEMI"): pass
            if self.cur().type in ("RBRACE","EOF"): break
            stmts.append(self.parse_stmt())
            while self.maybe("SEMI") or self.maybe("NEWLINE"): pass
        return stmts
    def parse_stmt(self) -> Stmt:
        t = self.cur()
        if t.type == "IF": return self.parse_if()
        if t.type == "WHILE": return self.parse_while()
        if t.type == "RETURN":
            self.eat("RETURN")
            if self.cur().type in ("NEWLINE","SEMI","RBRACE"): return ReturnStmt(None)
            return ReturnStmt(self.parse_expr())
        if t.type == "PRINT":
            self.eat("PRINT"); return PrintStmt(self.parse_expr())
        if t.type == "PRINT_SOURCE":
            self.eat("PRINT_SOURCE"); return PrintSourceStmt()
        if t.type == "MODIFY_LINE":
            self.eat("MODIFY_LINE"); ln = self.parse_expr(); nt = self.parse_expr(); return ModifyLineStmt(ln, nt)
        if t.type == "RECOMPILE_AND_GOTO":
            self.eat("RECOMPILE_AND_GOTO"); nm = self.eat("ID").value; return RecompileGotoStmt(nm)
        if t.type == "OPTIMIZE": self.eat("OPTIMIZE"); return OptimizeStmt()
        if t.type == "EVOLVE":
            self.eat("EVOLVE"); entry = self.eat("ID").value
            fitness = None
            if self.cur().type == "ID": fitness = self.eat("ID").value
            iters = int(self.eat("NUMBER").value)
            return EvolveStmt(entry, fitness, iters)
        if t.type == "SEND_SOURCE":
            self.eat("SEND_SOURCE"); tgt = self.parse_expr(); return SendSourceStmt(tgt)
        if t.type == "ID":
            name = self.eat("ID").value
            if self.maybe("OP") and self.toks[self.i-1].value == "=":
                return Assign(name, self.parse_expr())
            elif self.maybe("LPAREN"):
                args = []
                if self.cur().type != "RPAREN":
                    args.append(self.parse_expr())
                    while self.maybe("COMMA"): args.append(self.parse_expr())
                self.eat("RPAREN"); return CallStmt(name, args)
            else:
                raise SyntaxError(f"Unexpected token after identifier '{name}' at line {t.line}")
        raise SyntaxError(f"Unexpected token {t.type} at line {t.line}")
    def parse_if(self) -> IfStmt:
        self.eat("IF"); cond = self.parse_expr()
        if self.maybe("THEN"): pass
        then_body = self.parse_block_like(); else_body = None
        if self.maybe("ELSE"): else_body = self.parse_block_like()
        self.eat("END"); return IfStmt(cond, then_body, else_body)
    def parse_while(self) -> WhileStmt:
        self.eat("WHILE"); cond = self.parse_expr()
        if self.maybe("DO"): pass
        body = self.parse_block_like(); self.eat("END"); return WhileStmt(cond, body)
    def parse_block_like(self) -> List[Stmt]:
        if self.maybe("LBRACE"):
            blk = self.parse_block_until_rbrace(); self.eat("RBRACE"); return blk
        stmts = []
        while self.maybe("NEWLINE") or self.maybe("SEMI"): pass
        stmts.append(self.parse_stmt())
        while True:
            saved = self.cur()
            if saved.type in ("END","ELSE","EOF","RBRACE"): break
            if not (self.maybe("NEWLINE") or self.maybe("SEMI")): break
            while self.maybe("NEWLINE") or self.maybe("SEMI"): pass
            if self.cur().type in ("END","ELSE","EOF","RBRACE"): break
            stmts.append(self.parse_stmt())
        return stmts
    def parse_expr(self) -> 'Expr':
        return self.parse_equality()
    def parse_equality(self) -> 'Expr':
        expr = self.parse_rel()
        while self.cur().type == "OP" and self.cur().value in ("==","!="):
            op = self.eat("OP").value; expr = BinOp(expr, op, self.parse_rel())
        return expr
    def parse_rel(self) -> 'Expr':
        expr = self.parse_add()
        while self.cur().type == "OP" and self.cur().value in ("<","<=",">",">="):
            op = self.eat("OP").value; expr = BinOp(expr, op, self.parse_add())
        return expr
    def parse_add(self) -> 'Expr':
        expr = self.parse_mul()
        while self.cur().type == "OP" and self.cur().value in ("+","-"):
            op = self.eat("OP").value; expr = BinOp(expr, op, self.parse_mul())
        return expr
    def parse_mul(self) -> 'Expr':
        expr = self.parse_unary()
        while self.cur().type == "OP" and self.cur().value in ("*","/"):
            op = self.eat("OP").value; expr = BinOp(expr, op, self.parse_unary())
        return expr
    def parse_unary(self) -> 'Expr':
        if self.cur().type == "OP" and self.cur().value in ("+","-"):
            op = self.eat("OP").value; expr = self.parse_unary()
            return BinOp(Number(0), "-", expr) if op == "-" else expr
        return self.parse_primary()
    def parse_primary(self) -> 'Expr':
        t = self.cur()
        if t.type == "NUMBER": return Number(int(self.eat("NUMBER").value))
        if t.type == "STRING":
            raw = self.eat("STRING").value
            s = bytes(raw[1:-1], "utf-8").decode("unicode_escape")
            return StringLit(s)
        if t.type == "ID":
            name = self.eat("ID").value
            if self.maybe("LPAREN"):
                args = []
                if self.cur().type != "RPAREN":
                    args.append(self.parse_expr())
                    while self.maybe("COMMA"): args.append(self.parse_expr())
                self.eat("RPAREN"); return CallExpr(name, args)
            return Var(name)
        if t.type == "LPAREN":
            self.eat("LPAREN"); e = self.parse_expr(); self.eat("RPAREN"); return e
        raise SyntaxError(f"Unexpected token in expression: {t.type} at line {t.line}")

# ------------------ Exceptions ------------------
class RecompileJump(Exception):
    def __init__(self, func_name: str): self.func_name = func_name
class RuntimeLimit(Exception): pass
class ValidationError(Exception): pass

# ------------------ Audit Logger ------------------
class AuditLogger:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
    def log(self, kind: str, **fields):
        evt = {"ts_ns": time.time_ns(), "kind": kind}
        evt.update(fields); self.events.append(evt)
    def dump_json(self, path: str):
        with open(path, "w") as f: json.dump(self.events, f, indent=2)

# ------------------ Resource Contracts ------------------
def resource_contract(max_steps: Optional[int]=None, max_time_ms: Optional[int]=None):
    def deco(fn):
        def wrapper(self, *a, **kw):
            start_steps = self.steps
            start_ns = time.time_ns()
            out = fn(self, *a, **kw)
            end_ns = time.time_ns()
            if max_steps is not None and (self.steps - start_steps) > max_steps:
                raise RuntimeLimit(f"Resource contract breach: steps {(self.steps-start_steps)} > {max_steps}")
            if max_time_ms is not None and ((end_ns - start_ns)/1e6) > max_time_ms:
                raise RuntimeLimit(f"Resource contract breach: time {(end_ns-start_ns)/1e6:.1f}ms > {max_time_ms}ms")
            return out
        return wrapper
    return deco

# ------------------ Interpreter ------------------
class Interpreter:
    SIMPLE_CONST_RE = re.compile(r'\b(\d+)\s*([\+\-\*/])\s*(\d+)\b')
    INT_LITERAL_RE = re.compile(r'(?P<num>\b\d+\b)')
    OP_REPLACEMENTS = {'+':['-','+'], '-':['+','-'], '*':['*','+'], '/':['/','*'], '<':['<','>','<='], '>':['>','<','>=']}

    def __init__(self, source_lines: List[str],
                 max_steps: int = MAX_STEPS_DEFAULT,
                 max_recursion: int = MAX_RECURSION_DEFAULT,
                 max_recompiles: int = MAX_RECOMPILES_DEFAULT,
                 max_source_bytes: int = MAX_SOURCE_BYTES_DEFAULT,
                 allowed_hosts = None,
                 enable_network: bool = ENABLE_NETWORK_DEFAULT,
                 deterministic_seed: Optional[int] = None,
                 hmac_key: Optional[bytes] = None,
                 static_analyzer: Optional[Callable[[Program], List[str]]] = None,
                 audit: Optional[AuditLogger] = None):
        self.source_lines = source_lines[:]
        self.max_steps = max_steps
        self.max_recursion = max_recursion
        self.max_recompiles = max_recompiles
        self.max_source_bytes = max_source_bytes
        self.allowed_hosts = set(allowed_hosts or ALLOWED_HOSTS_DEFAULT)
        self.enable_network = enable_network
        self.recompile_count = 0
        self.globals: Dict[str,int] = {}
        self.steps = 0
        self.call_depth = 0
        self.program: Optional[Program] = None
        self._last_resource_check = 0
        self.rng = random.Random(deterministic_seed) if deterministic_seed is not None else random
        self.hmac_key = hmac_key
        self.static_analyzer = static_analyzer
        self.audit = audit or AuditLogger()

        self._validate_safe_code(self.source_lines)
        self.compile()

    # ---- Validation & memory ----
    def _validate_safe_code(self, lines: List[str]) -> None:
        total_bytes = sum(len(l)+1 for l in lines)
        if total_bytes > self.max_source_bytes:
            raise ValidationError(f"Source too large ({total_bytes} bytes > {self.max_source_bytes})")
        for i, ln in enumerate(lines, start=1):
            if len(ln) > MAX_LINE_LEN:
                raise ValidationError(f"Line {i} exceeds length limit ({len(ln)} > {MAX_LINE_LEN})")
            for pat in FORBIDDEN_PATTERNS:
                if re.search(pat, ln):
                    raise ValidationError(f"Line {i} contains forbidden characters/patterns")
        if not any(re.match(r'\s*FUNC\s+main\s*\(', l) for l in lines):
            raise ValidationError("Program must define FUNC main()")
        if self.hmac_key is not None:
            mac = hmac.new(self.hmac_key, ("\n".join(lines)+"\n").encode(), hashlib.sha256).hexdigest()
            self.audit.log("integrity", hmac=mac)

    def _check_memory(self) -> None:
        if self.steps - self._last_resource_check < 1000: return
        self._last_resource_check = self.steps
        if _HAS_PSUTIL:
            p = psutil.Process(); mem_pct = psutil.virtual_memory().percent
            if mem_pct >= MEMORY_PCT_LIMIT: raise RuntimeLimit(f"Memory usage too high: {mem_pct:.1f}%")
            rss = p.memory_info().rss / (1024*1024)
            if rss > MEMORY_SOFT_LIMIT_MB: raise RuntimeLimit(f"Process RSS too high: {rss:.0f} MB")
        elif _HAS_RESOURCE:
            usage_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if usage_kb > 1_500_000: raise RuntimeLimit("Memory usage exceeded soft limit (ru_maxrss)")
        elif _HAS_TRACEMALLOC:
            current, peak = tracemalloc.get_traced_memory()
            if peak > MEMORY_SOFT_LIMIT_MB * 1024 * 1024: raise RuntimeLimit("Memory usage exceeded soft limit (tracemalloc)")

    # ---- Compile / steps ----
    def compile(self):
        tokens = tokenize("\n".join(self.source_lines) + "\n")
        parser = Parser(tokens); program = parser.parse()
        if self.static_analyzer:
            warns = self.static_analyzer(program)
            for w in warns: self.audit.log("static_warn", msg=w)
        self.program = program

    def step(self, n=1):
        self.steps += n
        if self.steps > self.max_steps: raise RuntimeLimit(f"Step limit exceeded ({self.max_steps})")
        self._check_memory()

    # ---- Exec ----
    def call(self, name: str, args: List[int]) -> Optional[int]:
        self.step()
        if self.call_depth >= self.max_recursion: raise RuntimeLimit(f"Recursion depth exceeded ({self.max_recursion}).")
        if name not in self.program.functions: raise RuntimeError(f"Undefined function: {name}")
        f = self.program.functions[name]
        if len(args) != len(f.params): raise RuntimeError(f"Arity mismatch calling {name}: expected {len(f.params)} got {len(args)}")
        saved = {}
        for p,v in zip(f.params, args):
            saved[p] = self.globals.get(p, None); self.globals[p] = v
        self.call_depth += 1; self.audit.log("call_enter", func=name, args=args, depth=self.call_depth)
        try:
            ret = self.exec_block(f.body)
        finally:
            for p,prev in saved.items():
                if prev is None: self.globals.pop(p, None)
                else: self.globals[p] = prev
            self.call_depth -= 1; self.audit.log("call_exit", func=name, depth=self.call_depth)
        return ret

    def eval_expr(self, e: 'Expr') -> int:
        self.step()
        if isinstance(e, Number): return e.value
        if isinstance(e, Var): return int(self.globals.get(e.name, 0))
        if isinstance(e, StringLit): return 0
        if isinstance(e, BinOp):
            l = self.eval_expr(e.left); r = self.eval_expr(e.right); op = e.op
            if op == "+": return l + r
            if op == "-": return l - r
            if op == "*": return l * r
            if op == "/":
                if r == 0: raise RuntimeError("Division by zero")
                return int(l // r)
            if op == "<":  return 1 if (l <  r) else 0
            if op == "<=": return 1 if (l <= r) else 0
            if op == ">":  return 1 if (l >  r) else 0
            if op == ">=": return 1 if (l >= r) else 0
            if op == "==": return 1 if (l == r) else 0
            if op == "!=": return 1 if (l != r) else 0
            raise RuntimeError(f"Unknown operator {op}")
        if isinstance(e, CallExpr):
            vals = [self.eval_expr(a) for a in e.args]; ret = self.call(e.name, vals); return int(ret or 0)
        raise RuntimeError(f"Unknown expr: {type(e)}")

    def exec_block(self, stmts: List[Stmt]) -> Optional[int]:
        for s in stmts:
            r = self.exec_stmt(s)
            if r is not None: return r
        return None

    def exec_stmt(self, s: Stmt) -> Optional[int]:
        self.step()
        self.audit.log("exec", stmt=type(s).__name__, vars=dict(self.globals))
        if isinstance(s, Assign):
            self.globals[s.name] = int(self.eval_expr(s.expr)); return None
        if isinstance(s, PrintStmt):
            print(self.eval_expr(s.expr)); return None
        if isinstance(s, PrintSourceStmt):
            for idx, line in enumerate(self.source_lines, start=1): print(f"{idx:>4}: {line}")
            return None
        if isinstance(s, IfStmt):
            cond = self.eval_expr(s.cond)
            return self.exec_block(s.then_body) if cond != 0 else (self.exec_block(s.else_body) if s.else_body else None)
        if isinstance(s, WhileStmt):
            guard = 0
            while True:
                if guard > self.max_steps: raise RuntimeLimit("While-loop guard tripped")
                guard += 1; cond = self.eval_expr(s.cond)
                if cond == 0: break
                r = self.exec_block(s.body)
                if r is not None: return r
            return None
        if isinstance(s, CallStmt):
            _ = self.call(s.name, [self.eval_expr(a) for a in s.args]); return None
        if isinstance(s, ReturnStmt):
            return 0 if s.expr is None else int(self.eval_expr(s.expr))
        if isinstance(s, ModifyLineStmt):
            return self._do_modify_line(s)
        if isinstance(s, RecompileGotoStmt):
            self.recompile_count += 1
            if self.recompile_count > self.max_recompiles: raise RuntimeLimit("Too many recompilations.")
            raise RecompileJump(s.func_name)
        if isinstance(s, OptimizeStmt):
            self._optimize_source_in_place(); self.compile(); return None
        if isinstance(s, EvolveStmt):
            self._do_evolve(s); return None
        if isinstance(s, SendSourceStmt):
            self._do_send_source(s); return None
        raise RuntimeError(f"Unknown stmt: {type(s)}")

    def _fold_constants_in_line(self, line: str) -> str:
        def repl(m):
            a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
            try:
                if op == "+": return str(a + b)
                if op == "-": return str(a - b)
                if op == "*": return str(a * b)
                if op == "/": return str(a // b) if b != 0 else f"{a}/{b}"
            except Exception:
                return f"{a}{op}{b}"
            return f"{a}{op}{b}"
        for _ in range(2): line = self.SIMPLE_CONST_RE.sub(repl, line)
        line = re.sub(r'\b(\w+)\s*=\s*\1\s*\+\s*0\b', r'\1 = \1', line)
        line = re.sub(r'\b(\w+)\s*=\s*\1\s*-\s*0\b', r'\1 = \1', line)
        line = re.sub(r'\b(\w+)\s*=\s*\1\s*\*\s*1\b', r'\1 = \1', line)
        line = re.sub(r'\b(\w+)\s*=\s*\1\s*/\s*1\b', r'\1 = \1', line)
        return line
    def _optimize_source_in_place(self):
        self.source_lines[:] = [self._fold_constants_in_line(ln) for ln in self.source_lines]

    def _mutate_source_once(self, src_lines: List[str]) -> List[str]:
        lines = src_lines[:]; tries = 0
        while tries < 10:
            idx = self.rng.randrange(len(lines)); line = lines[idx]
            if line.strip() in ('{','}','END') or line.strip().startswith('FUNC '):
                tries += 1; continue
            mutated = line
            if self.rng.random() < 0.55:
                nums = list(re.finditer(r'(?P<num>\b\d+\b)', line))
                if nums:
                    m = self.rng.choice(nums); n = int(m.group('num'))
                    delta = self.rng.choice([-1,1]); n2 = max(0, n+delta)
                    mutated = line[:m.start()] + str(n2) + line[m.end():]
            else:
                for op, repls in self.OP_REPLACEMENTS.items():
                    if op in line:
                        mutated = line.replace(op, self.rng.choice(repls), 1); break
            if mutated != line:
                lines[idx] = mutated; return lines
            tries += 1
        return lines

    def _validate_safe_code_after_edit(self, candidate: List[str]):
        self._validate_safe_code(candidate)

    @resource_contract(max_steps=50_000, max_time_ms=2_000)
    def _do_evolve(self, s: EvolveStmt) -> None:
        iters = max(1, min(int(s.iterations), EVOLVE_MAX_ITERS_HARD))
        base_src = self.source_lines[:]
        base_score, _ = self._score_program(base_src, s.entry, s.fitness_func)
        best_src, best_score = base_src, base_score
        for _ in range(iters):
            cand = self._mutate_source_once(best_src)
            cand_score, ok = self._score_program(cand, s.entry, s.fitness_func)
            if ok and cand_score > best_score:
                best_src, best_score = cand, cand_score
        if best_src != self.source_lines:
            self._validate_safe_code_after_edit(best_src)
            self.source_lines[:] = best_src
            self.compile()

    def _score_program(self, src_lines: List[str], entry: str, fitness_func: Optional[str]) -> Tuple[int,bool]:
        try:
            self._validate_safe_code(src_lines)
        except Exception:
            return (-10**9, False)
        sand = Interpreter(
            src_lines[:],
            max_steps=min(self.max_steps, 100_000),
            max_recursion=self.max_recursion,
            max_recompiles=min(self.max_recompiles, 100),
            max_source_bytes=self.max_source_bytes,
            allowed_hosts=self.allowed_hosts,
            enable_network=False,
            deterministic_seed=12345,
            hmac_key=self.hmac_key,
            static_analyzer=self.static_analyzer
        )
        ok = True
        try:
            sand.call(entry, [])
        except RecompileJump as j:
            try:
                sand.compile(); sand.call(j.func_name, [])
            except Exception: ok = False
        except RuntimeLimit: ok = False
        except Exception: ok = False
        if ok and fitness_func and sand.program and fitness_func in sand.program.functions:
            try:
                f = sand.call(fitness_func, []); score = int(f or 0)
            except Exception: score = -10**8
        else:
            score = -sand.steps
        return (score, ok)

    def _do_modify_line(self, s: ModifyLineStmt) -> Optional[int]:
        line_no = int(self.eval_expr(s.line_no))
        new_text_val = s.new_text.value if isinstance(s.new_text, StringLit) else str(self.eval_expr(s.new_text))
        if line_no < 1 or line_no > len(self.source_lines): raise RuntimeError(f"MODIFY_LINE: line {line_no} out of range")
        candidate = self.source_lines[:]; candidate[line_no - 1] = new_text_val
        self._validate_safe_code_after_edit(candidate)
        self.audit.log("modify_line", line=line_no, new=new_text_val)
        self.source_lines[:] = candidate
        return None

    def _do_send_source(self, s: SendSourceStmt) -> None:
        if not self.enable_network: raise RuntimeError("Networking disabled by policy.")
        target = s.target.value if isinstance(s.target, StringLit) else str(self.eval_expr(s.target))
        parts = target.strip().split(":")
        if len(parts) != 2: raise RuntimeError('SEND_SOURCE: target must be "host:port"')
        host, port_s = parts[0], parts[1]
        if host not in self.allowed_hosts:
            raise RuntimeError(f"SEND_SOURCE: Host '{host}' not in allowlist {sorted(self.allowed_hosts)}")
        try:
            port = int(port_s)
            if not (1 <= port <= 65535): raise ValueError()
        except ValueError:
            raise RuntimeError("SEND_SOURCE: invalid port")
        data = ("\n".join(self.source_lines) + "\n").encode("utf-8")
        with socket.create_connection((host, port), timeout=3.0) as sock:
            sock.sendall(data)

# ------------------ Real-time Wrapper ------------------
class RealTimeInterpreter(Interpreter):
    def __init__(self, *a, max_execution_time_sec: Optional[int] = None, **kw):
        super().__init__(*a, **kw); self.max_execution_time_sec = max_execution_time_sec
    def call(self, name: str, args: List[int]) -> Optional[int]:
        if self.max_execution_time_sec is None:
            return super().call(name, args)
        def handler(signum, frame): raise TimeoutError()
        old = signal.signal(signal.SIGALRM, handler)
        signal.alarm(int(self.max_execution_time_sec))
        try:
            return super().call(name, args)
        except TimeoutError:
            raise RuntimeLimit("Hard execution time limit exceeded")
        finally:
            signal.alarm(0); signal.signal(signal.SIGALRM, old)

# ------------------ Demo ------------------
DEMO_SOURCE = """\
FUNC fitness() {
    RETURN 100 - (x - 12) * (x - 12)
}

FUNC main() {
    x = 5
    PRINT x
    IF x < 10 THEN
        MODIFY_LINE 2 "x = x + 1"
        RECOMPILE_AND_GOTO main
    END
    y = 2 + 3
    z = y * 1
    OPTIMIZE
    EVOLVE main fitness 10
    PRINT x
}
"""

def run_demo():
    audit = AuditLogger()
    interp = RealTimeInterpreter(
        DEMO_SOURCE.splitlines(),
        deterministic_seed=42,
        enable_network=False,
        hmac_key=b"demo-key",
        static_analyzer=lambda prog: [],
        audit=audit,
        max_execution_time_sec=5
    )
    entry = "main"
    while True:
        try:
            interp.call(entry, []); break
        except RecompileJump as j:
            interp.compile(); entry = j.func_name; continue
        except (RuntimeLimit, SyntaxError, ValidationError, RuntimeError) as e:
            print(f"[ERROR] {e}", file=sys.stderr); break
    # dump audit if desired
    # audit.dump_json("audit.json")

if __name__ == "__main__":
    run_demo()
