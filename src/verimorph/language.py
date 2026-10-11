"""Small, immutable integer AST and bounded recursive-descent parser."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import VeriMorphError

MAX_SOURCE = 65536
MAX_NODES = 4096
MAX_DEPTH = 48
MIN_INT = -(2**63)
MAX_INT = 2**63 - 1
OPS = ("+", "-", "*", "/", "<", "<=", ">", ">=", "==", "!=")


@dataclass(frozen=True, slots=True)
class Node:
    kind: str
    value: str | int = ""
    children: tuple[Node, ...] = ()


@dataclass(frozen=True, slots=True)
class Function:
    name: str
    params: tuple[str, ...]
    body: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Program:
    functions: tuple[Function, ...]

    def function(self, name: str) -> Function:
        for f in self.functions:
            if f.name == name:
                return f
        raise VeriMorphError("semantic", f"undefined function {name}")


@dataclass(frozen=True, slots=True)
class Token:
    text: str
    offset: int


TOKEN = re.compile(r"\s+|\#[^\n]*|[A-Za-z][A-Za-z0-9_]*|[0-9]+|==|!=|<=|>=|[{}(),;=+*/<>-]")
KEYWORDS = {"FUNC", "RETURN", "PRINT", "IF", "ELSE", "WHILE", "EVOLVE"}
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")


def integer(value: int) -> int:
    if type(value) is not int or not MIN_INT <= value <= MAX_INT:
        raise VeriMorphError("integer", "signed 64-bit overflow or non-integer")
    return value


def lex(source: str) -> tuple[Token, ...]:
    try:
        size = len(source.encode("utf-8"))
    except UnicodeError as e:
        raise VeriMorphError("lex", "invalid Unicode source") from e
    if len(source) > MAX_SOURCE or size > MAX_SOURCE:
        raise VeriMorphError("lex", "source exceeds 65536 bytes")
    tokens = []
    pos = 0
    while pos < len(source):
        m = TOKEN.match(source, pos)
        if m is None:
            raise VeriMorphError("lex", f"unexpected character at offset {pos}")
        text = m.group()
        if not text.isspace() and not text.startswith("#"):
            if len(text) > 64:
                raise VeriMorphError("lex", "token too long")
            tokens.append(Token(text, pos))
            if len(tokens) > MAX_NODES * 4:
                raise VeriMorphError("lex", "too many tokens")
        pos = m.end()
    return (*tokens, Token("<EOF>", len(source)))


class Parser:
    def __init__(self, source: str):
        self.tokens = lex(source)
        self.index = 0
        self.nodes = 0

    @property
    def current(self) -> str:
        return self.tokens[self.index].text

    def take(self, expected: str | None = None) -> str:
        value = self.current
        if value == "<EOF>" or expected is not None and value != expected:
            raise VeriMorphError(
                "parse", f"expected {expected}, got {value} at {self.tokens[self.index].offset}"
            )
        self.index += 1
        return value

    def name(self) -> str:
        value = self.take()
        if not NAME.fullmatch(value) or value in KEYWORDS:
            raise VeriMorphError("parse", f"invalid identifier {value}")
        return value

    def node(self, kind: str, value: str | int = "", children: tuple[Node, ...] = ()) -> Node:
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise VeriMorphError("parse", "AST node limit")
        return Node(kind, value, children)

    def guard(self, depth: int) -> None:
        if depth > MAX_DEPTH:
            raise VeriMorphError("parse", "nesting limit")

    def parse(self) -> Program:
        functions: list[Function] = []
        while self.current != "<EOF>":
            if len(functions) >= 128:
                raise VeriMorphError("parse", "function limit")
            self.take("FUNC")
            name = self.name()
            self.take("(")
            params = []
            if self.current != ")":
                params.append(self.name())
                while self.current == ",":
                    self.take(",")
                    params.append(self.name())
                    if len(params) > 16:
                        raise VeriMorphError("parse", "parameter limit")
            self.take(")")
            functions.append(Function(name, tuple(params), self.block(0)))
        program = Program(tuple(functions))
        validate_structure(program)
        return program

    def block(self, depth: int) -> tuple[Node, ...]:
        self.guard(depth)
        self.take("{")
        result = []
        while self.current != "}":
            result.append(self.statement(depth + 1))
        self.take("}")
        return tuple(result)

    def statement(self, depth: int) -> Node:
        self.guard(depth)
        tag = self.current
        if tag in ("RETURN", "PRINT"):
            self.take()
            expr = self.expression(0, depth + 1)
            self.take(";")
            return self.node(tag.lower(), children=(expr,))
        if tag == "IF":
            self.take()
            cond = self.expression(0, depth + 1)
            yes = self.node("block", children=self.block(depth + 1))
            no = self.node("block")
            if self.current == "ELSE":
                self.take()
                no = self.node("block", children=self.block(depth + 1))
            return self.node("if", children=(cond, yes, no))
        if tag == "WHILE":
            self.take()
            cond = self.expression(0, depth + 1)
            body = self.node("block", children=self.block(depth + 1))
            return self.node("while", children=(cond, body))
        if tag == "EVOLVE":
            self.take()
            value = self.take()
            if not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 1000:
                raise VeriMorphError("parse", "EVOLVE requires literal 1..1000")
            self.take(";")
            return self.node("evolve", int(value))
        name = self.name()
        self.take("=")
        expr = self.expression(0, depth + 1)
        self.take(";")
        return self.node("assign", name, (expr,))

    def expression(self, minimum: int, depth: int) -> Node:
        self.guard(depth)
        token = self.take()
        if token == "(":
            left = self.expression(0, depth + 1)
            self.take(")")
        elif token in ("-", "+"):
            if self.current.isascii() and self.current.isdigit():
                raw = int(self.take())
                left = self.node("number", integer(-raw if token == "-" else raw))
            else:
                operand = self.expression(5, depth + 1)
                if operand.kind == "number":
                    left = self.node(
                        "number",
                        integer(-int(operand.value) if token == "-" else int(operand.value)),
                    )
                else:
                    left = self.node("unary", token, (operand,))
        elif token.isascii() and token.isdigit():
            left = self.node("number", integer(int(token)))
        elif NAME.fullmatch(token) and token not in KEYWORDS:
            if self.current == "(":
                self.take()
                args = []
                if self.current != ")":
                    args.append(self.expression(0, depth + 1))
                    while self.current == ",":
                        self.take()
                        args.append(self.expression(0, depth + 1))
                        if len(args) > 16:
                            raise VeriMorphError("parse", "argument limit")
                self.take(")")
                left = self.node("call", token, tuple(args))
            else:
                left = self.node("var", token)
        else:
            raise VeriMorphError("parse", f"unexpected expression {token}")
        precedence = {
            "==": 1,
            "!=": 1,
            "<": 2,
            "<=": 2,
            ">": 2,
            ">=": 2,
            "+": 3,
            "-": 3,
            "*": 4,
            "/": 4,
        }
        while self.current in precedence and precedence[self.current] >= minimum:
            op = self.take()
            right = self.expression(precedence[op] + 1, depth + 1)
            left = self.node("binary", op, (left, right))
        return left


def parse(source: str) -> Program:
    return Parser(source).parse()


def walk(program: Program) -> tuple[tuple[str, Node], ...]:
    result = []
    stack = [
        (f"{f.name}/{i}", n, 0)
        for f in reversed(program.functions)
        for i, n in reversed(tuple(enumerate(f.body)))
    ]
    while stack:
        path, node, depth = stack.pop()
        if type(node) is not Node or type(node.children) is not tuple or depth > MAX_DEPTH:
            raise VeriMorphError("structure", "invalid node or depth")
        result.append((path, node))
        if len(result) > MAX_NODES:
            raise VeriMorphError("structure", "AST node limit")
        stack.extend(
            (f"{path}/{i}", child, depth + 1)
            for i, child in reversed(tuple(enumerate(node.children)))
        )
    return tuple(result)


EXPR = {"number", "var", "binary", "unary", "call"}
STMT = {"return", "print", "assign", "if", "while", "evolve"}


def validate_structure(program: Program) -> None:
    if (
        type(program) is not Program
        or type(program.functions) is not tuple
        or not 1 <= len(program.functions) <= 128
    ):
        raise VeriMorphError("structure", "invalid program")
    names = set()
    for f in program.functions:
        if (
            type(f) is not Function
            or not NAME.fullmatch(f.name)
            or f.name in KEYWORDS
            or f.name in names
        ):
            raise VeriMorphError("structure", "invalid/duplicate function")
        names.add(f.name)
        if (
            type(f.params) is not tuple
            or len(f.params) > 16
            or len(set(f.params)) != len(f.params)
            or any(not NAME.fullmatch(p) or p in KEYWORDS for p in f.params)
        ):
            raise VeriMorphError("structure", "invalid parameters")
        if type(f.body) is not tuple or any(n.kind not in STMT for n in f.body):
            raise VeriMorphError("structure", "invalid function body")
    for _, n in walk(program):
        if type(n.kind) is not str or type(n.value) not in (str, int):
            raise VeriMorphError("structure", "invalid node value")
        count = len(n.children)
        if n.kind == "number":
            if type(n.value) is not int:
                raise VeriMorphError("structure", "numeric literal required")
            integer(n.value)
            valid = count == 0
        elif n.kind in ("var", "assign", "call"):
            valid = (
                isinstance(n.value, str)
                and bool(NAME.fullmatch(n.value))
                and n.value not in KEYWORDS
                and (count == (1 if n.kind == "assign" else 0) if n.kind != "call" else count <= 16)
                and all(c.kind in EXPR for c in n.children)
            )
        elif n.kind in ("binary", "unary"):
            valid = (
                n.value in (OPS if n.kind == "binary" else ("+", "-"))
                and count == (2 if n.kind == "binary" else 1)
                and all(c.kind in EXPR for c in n.children)
            )
        elif n.kind in ("return", "print"):
            valid = n.value == "" and count == 1 and n.children[0].kind in EXPR
        elif n.kind in ("if", "while"):
            valid = (
                n.value == ""
                and count == (3 if n.kind == "if" else 2)
                and n.children[0].kind in EXPR
                and all(c.kind == "block" for c in n.children[1:])
            )
        elif n.kind == "block":
            valid = n.value == "" and all(c.kind in STMT for c in n.children)
        elif n.kind == "evolve":
            valid = type(n.value) is int and 1 <= n.value <= 1000 and count == 0
        else:
            valid = False
        if not valid:
            raise VeriMorphError("structure", f"invalid {n.kind} shape")


def expression_source(n: Node) -> str:
    if n.kind in ("number", "var"):
        return str(n.value)
    if n.kind == "unary":
        return f"({n.value}{expression_source(n.children[0])})"
    if n.kind == "binary":
        return f"({expression_source(n.children[0])} {n.value} {expression_source(n.children[1])})"
    if n.kind == "call":
        return f"{n.value}({', '.join(expression_source(c) for c in n.children)})"
    raise VeriMorphError("structure", "not an expression")


def statement_source(n: Node) -> str:
    if n.kind in ("return", "print"):
        return f"{n.kind.upper()} {expression_source(n.children[0])};"
    if n.kind == "assign":
        return f"{n.value} = {expression_source(n.children[0])};"
    if n.kind == "evolve":
        return f"EVOLVE {n.value};"
    cond = expression_source(n.children[0])
    body = " ".join(statement_source(c) for c in n.children[1].children)
    if n.kind == "while":
        return f"WHILE {cond} {{ {body} }}"
    other = " ".join(statement_source(c) for c in n.children[2].children)
    return f"IF {cond} {{ {body} }} ELSE {{ {other} }}"


def canonical_source(program: Program) -> str:
    validate_structure(program)
    return (
        "\n".join(
            f"FUNC {f.name}({', '.join(f.params)}) {{ {' '.join(statement_source(n) for n in f.body)} }}"
            for f in program.functions
        )
        + "\n"
    )
