from typing import NamedTuple, List, Tuple
from datetime import datetime
from enum import Enum
from functools import partial
from derp import rec, lit, empty_string, Grammar, RegexTokenizer, Token
from derp.parsers import BaseParser, empty_parser, Epsilon, Token
from derp import unpack
from datetime import date, datetime

from functools import reduce
from operator import or_
from math import pow


class Tokenizer(RegexTokenizer):
    patterns = tuple(p for p in RegexTokenizer.patterns if not p[0]=='NUMBER')
    patterns += (
        ('DATE', r'\d\d/\d\d/\d\d'),
        ('TIME', r'\d\d:\d\d:\d\d'),
        ('FLOAT',r'(\d*)\.\d*(E[+-]\d+)?'),
        ('INT', r'0|[1-9](\d*)')
    )
    

tokenizer = Tokenizer()


class Header(NamedTuple):
    code: str
    version: str
    date_time: datetime
    dump_id: int
    n_histories: int
    n_random_numbers: int
    title: str
    n_tallies: str
    tally_numbers: List[int]
    n_peturbations: int

class TFC(NamedTuple):
    n: int
    bin_indices: Tuple[int]
    data: Tuple[Tuple[int, float, float, float], ...]

class BinType(Enum):
    default = ''
    cumulative = 'c'
    total = 't'
    
class BinInfo(NamedTuple):
    n: int
    type: BinType

class Hist(NamedTuple):
    n: int
    f: int
    values: Tuple[float, ...]
    bin_type: BinType
        
class Tally(NamedTuple):
    problem_id: int
    particle_type: int
    n_numbers: int
    numbers: Tuple[int]
    n_total_vs_direct: int
    users: BinInfo
    segments: BinInfo
    multipliers: BinInfo
    cosines: Hist
    energies: Hist
    times: Hist
    data: Tuple[float]
    tfc: TFC
        
class KCODE(NamedTuple):
    n_cycles: int
    n_settle_cycles: int
    n_cycle_variables: int
    data: Tuple[Tuple[float, ...], ...]
        
    
class MCTAL(NamedTuple):
    header: Header
    tallies: List[Tally]
    kcode: KCODE
    

class Exact(BaseParser, fields='string'):
    def derive(self, token: Token) -> BaseParser:
        return Epsilon.from_value(token.second) if token.second == self.string else empty_parser

    def derive_null(self) -> frozenset:
        return frozenset()

exact = Exact

def mask(mask_string: str):
    mask_string = mask_string.replace('_', '')
    flags = [c == '1' for c in mask_string]
    def functor(args):
        return tuple((x for x, f in zip(unpack(args, len(flags)), flags) if f))
    return functor

g = Grammar("mctal")

g.NL = lit('NEWLINE')
g.int = lit('INT') >> int  
g.float = lit('FLOAT') >> float

def emit_date(date):
    return datetime.strptime(date, "%m/%d/%y").date()
g.date = lit('DATE') >> emit_date

def emit_time(time):
    return datetime.strptime(time, "%H:%M:%S").time()
g.time = lit('TIME') >> emit_time

def emit_datetime(args):
    return datetime.combine(*args)
g.datetime = (g.date & g.time) >> emit_datetime

non_newline_parsers = [lit(x) for x in ('INT', 'FLOAT','ID', 'LIT', 'DATE', 'TIME', 
                                        *Tokenizer.OP_CHARACTERS, *Tokenizer.PAREN_CHARACTERS)]
g.non_newline = reduce(or_, non_newline_parsers)
g.version = (lit('INT') | lit('ID'))[1:]

def make_list(parser):
    line = (parser[1:] & lit('NEWLINE')) >> (lambda args: args[0])
    return line[...] >> (lambda a: tuple([x for y in a for x in y]))
g.description = (g.non_newline[...]) >> ' '.join

def emit_header(args):
    program, version, datetime, dump_id, n_histories, n_random_numbers, _, description, _, \
    _, n_tal, opt_npert_pair, _, lst = unpack(args, 14)
    return Header(program, version, datetime, dump_id, n_histories, n_random_numbers, 0,
                  n_tal, lst, 0)

g.header = (lit('ID') & g.version & g.datetime & g.int & g.int & g.int & g.NL &\
            g.description & g.NL &\
            exact('ntal') & g.int & ~(exact('npert') & g.int) & g.NL &\
            make_list(g.int)) >> emit_header

def bin_type(name):
    return exact(name)>>(lambda a: BinType.default) | \
           exact(f'{name}c')>>(lambda a: BinType.cumulative) | \
           exact(f'{name}t')>>(lambda a: BinType.total)

def typed_bin_info(name):
    def f(args):
        bin_type, n, _ = unpack(args, 3)
        return BinInfo(n, bin_type)
    return (bin_type(name) & g.int & g.NL) >> f
        
def typed_hist(name):
    def f(args):
        bin_type, n, f, _, bins = unpack(args, 5)
        if not f:
            f = 0
        return Hist(n, f, bins, bin_type)
    return (bin_type(name) & g.int & ~g.int & g.NL & make_list(g.float)) >> f


def bins(name):
    return exact(name) | exact(f'{name}c') | exact(f'{name}t') # TODO use this info in namedtuple

def emit_tally(args):
    _, pname, i, _, f, d, u, s, m, c, e, t, vals, tfc = unpack(args, 14)
    return Tally(pname, i, *f, *d, u, s, m, c, e, t, *vals, tfc)

def emit_tfc(args):
    _, n, jtf, _, data = unpack(args, 5)
    data = tuple((x, *y) for x, y in data)
    return TFC(n, jtf, data)

g.tally =  (exact('tally') & g.int & g.int & g.NL &\
            (exact('f') & g.int & g.NL & make_list(g.int)) >> mask('0101') &\
            (exact('d') & g.int & g.NL) >> mask('010') & \
            typed_bin_info('u') &\
            typed_bin_info('s') & \
            typed_bin_info('m') & \
            typed_hist('c') & \
            typed_hist('e') & \
            typed_hist('t') & \
            (exact('vals') & g.NL & make_list(g.float[2])) >> mask('001') & \
            (exact('tfc') & g.int & g.int[8] & g.NL & make_list(g.int & g.float[3])) >> emit_tfc
           ) >> emit_tally

g.kcode = (exact('kcode') & g.int & g.int & g.int & g.NL & make_list(g.float)) >> mask('011101') >> KCODE

def emit_mctal(args):
    header, tallies, opt_kcode, _ = unpack(args, 4)
    if opt_kcode == '':
        opt_kcode = None
    return MCTAL(header, tallies, opt_kcode)

g.mctal = (g.header & g.tally[...] & ~g.kcode & lit('ENDMARKER')) >> emit_mctal
g.freeze()