import logging
import traceback
logger = logging.getLogger(__name__)
from ast_ import ASTNode, OperatorNode, RangeNode, OperandNode, FunctionNode
from networkx.classes.digraph import DiGraph
from tokenizer import Tokenizer, Token

class Cell:
    """
    Class responsible for creating cell objects from source addresses
    """

    def __init__(self ,address):
        """
        Each cell object is initalized with:
        - address, excel formula, value, rpn formula, col_field
        @param address:
        """
        self.address = address
        self.value = None
        self.prec = []
        self.hardcode = None
        self._formula = None
        self.rpn = []
        self.tree = None

    def __repr__(self):
        '''Represents a cell object by outputting the address, value and excel formula'''
        cell_str = 'A:{}, V:{}, F:{}'.format(self.address ,self.value ,self.formula)
        return cell_str

    @property
    def formula(self):
        return self._formula

    @formula.setter
    def formula(self, excel_formula):
        '''
        If excel formula is set, this TRIGGERS creation of rpn formula and tree
        @param excel_formula: excel formula as a string
        @return: rpn formula
        '''
        self._formula = excel_formula
        logging.debug("Processing RPN for formula {} at cell {}".format(excel_formula,self))

        if str(excel_formula).startswith(('=','+')):
           self.rpn = self.make_rpn(excel_formula)
           self.hardcode = False
           self.createPrec() # creates list of precedents (who do I depend on)
        else:
            logging.debug("Formula does not start with = or +. Creating a hardcode cell")
            tok = Token(self.address,Token.LITERAL,None)
            self.rpn.append(OperandNode(tok))
            self.hardcode = True

        logging.info("RPN is: {}".format(self.rpn))


    def createPrec(self):
        for node in self.rpn:
            if isinstance(node,RangeNode):
                self.prec.append(node.token.value)

    # def traverse(self, tree):
    #
    #     code = []
    #
    #     root = list(tree.nodes()).pop()
    #
    #     for child in list(tree.predecessors(root)):
    #         if isinstance(child,FunctionNode):
    #             self.traverse(child)
    #         elif isinstance(child,RangeNode):
    #             self.traverse(child)
    #     make_code(children)
    #     code.append(make_cod)
    #
    #     return code

    def make_node(self, token):
        sheet = self.address.split('!')[0]
        if token.type == Token.OPERAND and token.subtype == Token.RANGE and '!' not in token.value:
            token.value = '{}!{}'.format(sheet, token.value)
            return ASTNode.create(token)
        else:
            return ASTNode.create(token)

    def make_rpn(self, expression):
        """
        Parse an excel formula expression into reverse polish notation

        Core algorithm taken from wikipedia with varargs extensions from
        http://www.kallisti.net.nz/blog/2008/02/extension-to-the-shunting-yard-
            algorithm-to-allow-variable-numbers-of-arguments-to-functions/
        """

        """
                Parse an excel formula expression into reverse polish notation

                Core algorithm taken from wikipedia with varargs extensions from
                http://www.kallisti.net.nz/blog/2008/02/extension-to-the-shunting-yard-
                    algorithm-to-allow-variable-numbers-of-arguments-to-functions/
                """

        lexer = Tokenizer(expression)
        logging.info("Tokens created succesfully")

        # amend token stream to ease code production
        tokens = []
        for token, next_token in zip(lexer.items, lexer.items[1:] + [None]):

            if token.matches(Token.FUNC, Token.OPEN):
                tokens.append(token)
                token = Token('(', Token.PAREN, Token.OPEN)

            elif token.matches(Token.FUNC, Token.CLOSE):
                token = Token(')', Token.PAREN, Token.CLOSE)

            elif token.matches(Token.ARRAY, Token.OPEN):
                tokens.append(token)
                tokens.append(Token('(', Token.PAREN, Token.OPEN))
                tokens.append(Token('', Token.ARRAYROW, Token.OPEN))
                token = Token('(', Token.PAREN, Token.OPEN)

            elif token.matches(Token.ARRAY, Token.CLOSE):
                tokens.append(token)
                token = Token(')', Token.PAREN, Token.CLOSE)

            elif token.matches(Token.SEP, Token.ROW):
                tokens.append(Token(')', Token.PAREN, Token.CLOSE))
                tokens.append(Token(',', Token.SEP, Token.ARG))
                tokens.append(Token('', Token.ARRAYROW, Token.OPEN))
                token = Token('(', Token.PAREN, Token.OPEN)

            elif token.matches(Token.PAREN, Token.OPEN):
                token.value = '('

            elif token.matches(Token.PAREN, Token.CLOSE):
                token.value = ')'

            tokens.append(token)

        output = []
        stack = []
        were_values = []
        arg_count = []

        # shunting yard start
        for token in tokens:
            if token.type == token.OPERAND:
                output.append(self.make_node(token))
                if were_values:
                    were_values[-1] = True

            elif token.type != token.PAREN and token.subtype == token.OPEN:

                if token.type in (token.ARRAY, Token.ARRAYROW):
                    token = Token(token.type, token.type, token.subtype)

                stack.append(token)
                arg_count.append(0)
                if were_values:
                    were_values[-1] = True
                were_values.append(False)

            elif token.type == token.SEP:

                while stack and (stack[-1].subtype != token.OPEN):
                    output.append(self.make_node(stack.pop()))

                if not len(were_values):
                    raise FormulaParserError(
                        "Mismatched or misplaced parentheses")

                were_values.pop()
                arg_count[-1] += 1
                were_values.append(False)

            elif token.is_operator:

                while stack and stack[-1].is_operator:
                    if token.precedence < stack[-1].precedence:
                        output.append(self.make_node(stack.pop()))
                    else:
                        break

                stack.append(token)

            elif token.subtype == token.OPEN:
                assert token.type in (token.FUNC, token.PAREN, token.ARRAY)
                stack.append(token)

            elif token.subtype == token.CLOSE:

                while stack and stack[-1].subtype != Token.OPEN:
                    output.append(self.make_node(stack.pop()))

                if not stack:
                    raise FormulaParserError(
                        "Mismatched or misplaced parentheses")

                stack.pop()

                if stack and stack[-1].is_funcopen:
                    f = self.make_node((stack.pop()))
                    f.num_args = arg_count.pop() + int(were_values.pop())
                    output.append(f)

            else:
                assert token.type == token.WSPACE, \
                    'Unexpected token: {}'.format(token)

        while stack:
            if stack[-1].subtype in (Token.OPEN, Token.CLOSE):
                raise FormulaParserError("Mismatched or misplaced parentheses")

            output.append(self.make_node(stack.pop()))
        return output

    def build_ast(self):
        """build an AST from an Excel formula

        :param rpn_expression: a string formula or the result of parse_to_rpn()
        :return: AST which can be used to generate code
        """

        # use a directed graph to store the syntax tree
        tree = DiGraph()

        # production stack
        stack = []

        for node in self.rpn:
            # The graph does not maintain the order of adding nodes/edges, so
            # add an attribute 'pos' so we can always sort to the correct order

            # node.ast = tree
            if isinstance(node, OperatorNode):
                if node.token.type == node.token.OP_IN:
                    try:
                        arg2 = stack.pop()
                        arg1 = stack.pop()
                    except IndexError:
                        raise FormulaParserError(
                            "'{}' operator missing operand".format(
                                node.token.value))
                    tree.add_node(arg1, pos=0)
                    tree.add_node(arg2, pos=1)
                    tree.add_edge(arg1, node)
                    tree.add_edge(arg2, node)
                else:
                    try:
                        arg1 = stack.pop()
                    except IndexError:
                        raise FormulaParserError(
                            "'{}' operator missing operand".format(
                                node.token.value))
                    tree.add_node(arg1, pos=1)
                    tree.add_edge(arg1, node)

            elif isinstance(node, FunctionNode):
                if node.num_args:
                    args = stack[-node.num_args:]
                    del stack[-node.num_args:]
                    for i, a in enumerate(args):
                        tree.add_node(a, pos=i)
                        tree.add_edge(a, node)
            else:
                tree.add_node(node, pos=0)
            stack.append(node)

        assert 1 == len(stack)

        #Set tree attribute of cell object
        self.tree = tree

    def calculate(self):
        lam = 'lambda {}:{}'.format(args, python_code)
        print(lam)


# if __name__ == "__main__":

