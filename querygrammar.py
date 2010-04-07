from lepl import *

def makeCall(*args):
    return args

def binOps(args):
    while len(args)>1:
        args[:3]=[[args[1],args[0],args[2]]]
    return args[0]

def makeString(args):
    return ['__str__',args[0]]

spaces=~Star(Space())
sglQuotedString=Drop("'")&Regexp(r"[^\'\\]*")&Drop("'") > makeString
name=Regexp('[A-Za-z][A-Za-z0-9]*')
expr=Delayed()
with Separator(spaces):
    comma=Drop(",")
    atomOrCall = ((name &
                   Drop("(") &
                   expr[:,comma] &
                   Drop(")") > list) |
                  name |
                  sglQuotedString)
    binOperator=Or(Literal("=="),
                   Literal("in"),
                   Literal("not in")) 
    binOp=atomOrCall[:,binOperator]> binOps
    andExpr=binOp[:,Literal("&")] > binOps
    orExpr=andExpr[:,Literal("|")] > binOps
expr += orExpr

parser=expr.string_parser()

def interpret_query(ast,symbols):
    if isinstance(ast,basestring):
        return symbols[ast]
    elif ast[0]=='__str__':
        return ast[1]
    else:
        args=[interpret_query(ast1,symbols) for ast1 in ast[1:]]
        return symbols[ast[0]](*args)

def make_query(s,symboltab):
    ast=parser(s)[0]
    return interpret_query(ast,symboltab)

class Functor(object):
    __slots__=['f','args']
    def __init__(self,f,*args):
        self.f=f
        self.args=args
    def __call__(self,x):
        argvals=[a(x) for a in args]
        return self.f(*argvals)

class Accessor(object):
    __slots__=['key']
    def __init__(self,key):
        self.key=key
    def __call__(self,x):
        return x.get(key,None)

class FunctorOp(object):
    __slots__=['f']
    def __init__(self,f):
        self.f=f
    def __call__(self,*args):
        return Functor(f,*args)
