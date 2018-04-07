from pygments.lexer import RegexLexer
from pygments.token import *

class CustomLexer(RegexLexer):
    name = 'Diff'
    aliases = ['diff']
    filenames = ['*.diff']

    tokens = {
        'root': [
            (r'C .*\n', Comment),
            (r'.*\n', Text),
        ]
    }
