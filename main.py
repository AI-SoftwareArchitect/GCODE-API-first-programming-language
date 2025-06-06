import sys
import subprocess
import os
import re
import json

def tokenize(code):
    token_spec = [
        ('TRIPLE_STRING', r'"""(?:[^"\\]|\\.|"(?!"")|""(?!""))*"""'),
        ('STRING',   r'"([^"\\]|\\.)*"'),
        ('NUMBER',   r'\d+'),
        ('ID',       r'[A-Za-z_][A-Za-z0-9_]*'),
        ('NEWLINE',  r'\n'),
        ('SKIP',     r'[ \t]+'),
        ('SYMBOL',   r'[{}();=,+\-*/<>\[\].]'),
        ('UNKNOWN',  r'.'),
    ]
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_spec)
    for mo in re.finditer(tok_regex, code):
        kind = mo.lastgroup
        value = mo.group()
        if kind == 'SKIP' or kind == 'NEWLINE':
            continue
        yield (kind, value)

class Parser:
    def __init__(self, tokens):
        self.tokens = list(tokens)
        self.pos = 0

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def advance(self):
        self.pos += 1

    def expect(self, kind, value=None):
        tok = self.peek()
        if tok is None or tok[0] != kind or (value is not None and tok[1] != value):
            raise SyntaxError(f"Expected: {kind} {value}, found: {tok}")
        self.advance()
        return tok[1]

    def parse(self):
        nodes = []
        while self.peek():
            tok = self.peek()
            if tok[0] == 'ID' and tok[1] == 'api':
                nodes.append(self.parse_api())
            else:
                self.advance()
        return nodes

    def parse_api(self):
        self.expect('ID', 'api')
        name = self.expect('ID')
        self.expect('SYMBOL', '{')
        globals_ = []
        inits = []
        routes = []
        while True:
            tok = self.peek()
            if tok is None:
                raise SyntaxError("API block not closed")
            if tok[0] == 'SYMBOL' and tok[1] == '}':
                self.advance()
                break
            if tok[0] == 'ID' and tok[1] == 'var':
                globals_.append(self.parse_var())
            elif tok[0] == 'ID' and tok[1] == 'route':
                routes.append(self.parse_route())
            elif tok[0] == 'ID':
                inits.append(self.parse_assign_or_call())
            else:
                self.advance()
        return {'type': 'api', 'name': name, 'globals': globals_, 'inits': inits, 'routes': routes}

    def parse_var(self):
        self.expect('ID', 'var')
        typ = self.expect('ID')  # int, list, string, etc.
        if typ == 'list':
            subtype = self.expect('ID')  # int, string, etc.
            name = self.expect('ID')
            self.expect('SYMBOL', ';')
            return {'type': 'var', 'vartype': 'list', 'subtype': subtype, 'name': name}
        else:
            name = self.expect('ID')
            init_value = None
            if self.peek() and self.peek()[0] == 'SYMBOL' and self.peek()[1] == '=':
                self.advance()  # consume '='
                init_value = self.parse_expr()
            self.expect('SYMBOL', ';')
            return {'type': 'var', 'vartype': typ, 'name': name, 'value': init_value}

    def parse_expr(self):
        left = self.parse_factor()
        tok = self.peek()
        while tok and tok[0] == 'SYMBOL' and tok[1] in ('+', '-'):
            op = tok[1]
            self.advance()
            right = self.parse_factor()
            left = {'type': 'binop', 'op': op, 'left': left, 'right': right}
            tok = self.peek()
        return left

    def parse_factor(self):
        left = self.parse_term()
        tok = self.peek()
        while tok and tok[0] == 'SYMBOL' and tok[1] in ('*', '/'):
            op = tok[1]
            self.advance()
            right = self.parse_term()
            left = {'type': 'binop', 'op': op, 'left': left, 'right': right}
            tok = self.peek()
        return left

    def parse_term(self):
        tok = self.peek()
        if tok[0] == 'NUMBER':
            self.advance()
            return {'type': 'number', 'value': int(tok[1])}
        elif tok[0] == 'ID':
            name = self.expect('ID')
            # Array access: users[0]
            if self.peek() and self.peek()[0] == 'SYMBOL' and self.peek()[1] == '[':
                self.expect('SYMBOL', '[')
                index = self.parse_expr()
                self.expect('SYMBOL', ']')
                return {'type': 'arrayref', 'name': name, 'index': index}
            else:
                return {'type': 'varref', 'name': name}
        elif tok[0] == 'SYMBOL' and tok[1] == '(':
            self.advance()
            expr = self.parse_expr()
            self.expect('SYMBOL', ')')
            return expr
        else:
            raise SyntaxError(f"Expected: number, variable or (, found: {tok}")

    def parse_route_params(self):
        """Parse route parameters like REQ_BODY [int foo, string bar] veya eski [int foo]"""
        params = []
        # REQ_BODY desteği
        if self.peek() and self.peek()[0] == 'ID' and self.peek()[1] == 'REQ_BODY':
            self.expect('ID', 'REQ_BODY')
            # Eğer hemen sonra köşeli parantez varsa, parametreleri oku
            if self.peek() and self.peek()[0] == 'SYMBOL' and self.peek()[1] == '[':
                self.expect('SYMBOL', '[')
                while True:
                    if self.peek() and self.peek()[0] == 'SYMBOL' and self.peek()[1] == ']':
                        self.expect('SYMBOL', ']')
                        break
                    param_type = self.expect('ID')
                    param_name = self.expect('ID')
                    params.append({'type': param_type, 'name': param_name})
                    if self.peek() and self.peek()[0] == 'SYMBOL' and self.peek()[1] == ',':
                        self.advance()
                    elif self.peek() and self.peek()[0] == 'SYMBOL' and self.peek()[1] == ']':
                        continue
                    else:
                        break
            else:
                # Eski tek parametreli REQ_BODY desteği (varsayılan)
                params.append({'type': 'int', 'name': 'newuser'})
            return params
        # Eski köşeli parantezli parametre desteği
        if self.peek() and self.peek()[0] == 'SYMBOL' and self.peek()[1] == '[':
            self.expect('SYMBOL', '[')
            while True:
                if self.peek() and self.peek()[0] == 'SYMBOL' and self.peek()[1] == ']':
                    self.expect('SYMBOL', ']')
                    break
                param_type = self.expect('ID')
                param_name = self.expect('ID')
                params.append({'type': param_type, 'name': param_name})
                if self.peek() and self.peek()[0] == 'SYMBOL' and self.peek()[1] == ',':
                    self.advance()
                elif self.peek() and self.peek()[0] == 'SYMBOL' and self.peek()[1] == ']':
                    continue
                else:
                    break
        return params

    def parse_route(self):
        self.expect('ID', 'route')
        path_tok = self.peek()
        if path_tok and (path_tok[0] == 'STRING' or path_tok[0] == 'TRIPLE_STRING'):
            path = self.expect(path_tok[0])
        else:
            raise SyntaxError(f"Expected string for route path, found: {path_tok}")
        
        method = self.expect('ID')
        
        # Parse optional parameters (REQ_BODY desteği)
        params = self.parse_route_params()
        
        self.expect('SYMBOL', '{')
        body = []
        while True:
            tok = self.peek()
            if tok is None:
                raise SyntaxError("Route block not closed")
            if tok[0] == 'SYMBOL' and tok[1] == '}':
                self.advance()
                break
            if tok[0] == 'ID' and tok[1] == 'return':
                body.append(self.parse_return())
            elif tok[0] == 'ID' and tok[1] == 'if':
                body.append(self.parse_if())
            elif tok[0] == 'ID':
                body.append(self.parse_assign_or_call())
            else:
                self.advance()
        
        if path_tok[0] == 'TRIPLE_STRING':
            path = path[3:-3]
        else:
            path = path.strip('"')
        return {'type': 'route', 'path': path, 'method': method, 'params': params, 'body': body}

    def parse_if(self):
        """Parse if conditions like: if (user > 0) { ... }"""
        self.expect('ID', 'if')
        self.expect('SYMBOL', '(')
        condition = self.parse_condition()
        self.expect('SYMBOL', ')')
        self.expect('SYMBOL', '{')
        
        then_body = []
        while True:
            tok = self.peek()
            if tok is None or (tok[0] == 'SYMBOL' and tok[1] == '}'):
                if tok:
                    self.advance()  # consume '}'
                break
            if tok[0] == 'ID' and tok[1] == 'return':
                then_body.append(self.parse_return())
            elif tok[0] == 'ID':
                then_body.append(self.parse_assign_or_call())
            else:
                self.advance()
        
        else_body = []
        if self.peek() and self.peek()[0] == 'ID' and self.peek()[1] == 'else':
            self.advance()  # consume 'else'
            self.expect('SYMBOL', '{')
            while True:
                tok = self.peek()
                if tok is None or (tok[0] == 'SYMBOL' and tok[1] == '}'):
                    if tok:
                        self.advance()  # consume '}'
                    break
                if tok[0] == 'ID' and tok[1] == 'return':
                    else_body.append(self.parse_return())
                elif tok[0] == 'ID':
                    else_body.append(self.parse_assign_or_call())
                else:
                    self.advance()
        
        return {'type': 'if', 'condition': condition, 'then': then_body, 'else': else_body}

    def parse_condition(self):
        """Parse conditions like: user > 0, name == "admin" """
        left = self.parse_term()
        tok = self.peek()
        if tok and tok[0] == 'SYMBOL' and tok[1] in ['>', '<', '=']:
            op = self.expect('SYMBOL')  # Doğru şekilde operatorü al
            if op == '=' and self.peek() and self.peek()[0] == 'SYMBOL' and self.peek()[1] == '=':
                self.advance()  # consume second '='
                op = '=='
            right = self.parse_term()
            return {'type': 'compare', 'left': left, 'op': op, 'right': right}
        return left

    def parse_assign_or_call(self):
        name = self.expect('ID')
        tok = self.peek()
        if tok is None:
            raise SyntaxError("Unexpected end of input in assign or call")
        if tok[0] == 'SYMBOL' and tok[1] == '.':
            self.advance()
            func = self.expect('ID')
            self.expect('SYMBOL', '(')
            arg = self.parse_expr()
            self.expect('SYMBOL', ')')
            self.expect('SYMBOL', ';')
            return {'type': 'call', 'name': name, 'func': func, 'arg': arg}
        elif tok[0] == 'SYMBOL' and tok[1] == '=':
            self.advance()
            expr = self.parse_expr()
            self.expect('SYMBOL', ';')
            return {'type': 'assign', 'name': name, 'expr': expr}
        elif tok[0] == 'SYMBOL' and tok[1] == ';':
            # Desteklenmeyen tek başına değişken satırı (ör: users;)
            self.advance()
            return {'type': 'noop'}
        else:
            raise SyntaxError(f"Unexpected expression: {tok}")

    def parse_return(self):
        self.expect('ID', 'return')
        parts = []
        while True:
            tok = self.peek()
            if tok is None:
                break
            if tok[0] == 'SYMBOL' and tok[1] == ';':
                self.advance()
                break
            if tok[0] == 'STRING' or tok[0] == 'TRIPLE_STRING':
                val = self.expect(tok[0])
                if tok[0] == 'TRIPLE_STRING':
                    val = val[3:-3]
                else:
                    val = val.strip('"')
                parts.append({'type': 'str', 'value': val})
            elif tok[0] == 'ID':
                name = self.expect('ID')
                # Check for array access
                if self.peek() and self.peek()[0] == 'SYMBOL' and self.peek()[1] == '[':
                    self.expect('SYMBOL', '[')
                    index = self.parse_expr()
                    self.expect('SYMBOL', ']')
                    parts.append({'type': 'arrayref', 'name': name, 'index': index})
                else:
                    parts.append({'type': 'varref', 'name': name})
            elif tok[0] == 'SYMBOL' and tok[1] == '+':
                self.advance()
            else:
                raise SyntaxError(f"Unexpected token in return: {tok}")
        return {'type': 'return', 'parts': parts}

def expr_to_c(expr):
    if expr['type'] == 'number':
        return str(expr['value'])
    elif expr['type'] == 'varref':
        return expr['name']
    elif expr['type'] == 'arrayref':
        return f'{expr["name"]}[{expr_to_c(expr["index"])}]'
    elif expr['type'] == 'binop':
        return f'({expr_to_c(expr["left"])} {expr["op"]} {expr_to_c(expr["right"])})'
    else:
        raise Exception("Unknown expr type")

def condition_to_c(condition):
    """Parse conditions like: user > 0, name == "admin" """
    left = condition['left']
    right = condition['right']
    op = condition['op']

    if left['type'] == 'varref' and right['type'] == 'varref':
        return f"{left['name']} {op} {right['name']}"
    elif left['type'] == 'varref' and right['type'] == 'number':
        return f"{left['name']} {op} {right['value']}"
    elif left['type'] == 'number' and right['type'] == 'varref':
        return f"{left['value']} {op} {right['name']}"
    elif left['type'] == 'string' and right['type'] == 'string' and op == '==':
        return f'strcmp({expr_to_c(left)}, {expr_to_c(right)}) == 0'
    else:
        return f"{expr_to_c(condition['left'])} {op} {expr_to_c(condition['right'])}"

def return_parts_to_c(parts):
    # Build format string and arguments for sprintf
    fmt = ""
    args = []
    for part in parts:
        if part['type'] == 'str':
            s = part['value'].replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            fmt += s
        elif part['type'] == 'varref':
            fmt += "%d"
            args.append(part['name'])
        elif part['type'] == 'arrayref':
            fmt += "%d"
            args.append(f"{part['name']}[{expr_to_c(part['index'])}]")
    
    if args:
        argstr = ', '.join(args)
        return f'sprintf(resp, "{fmt}", {argstr});'
    else:
        return f'strcpy(resp, "{fmt}");'

def generate_json_parser(params):
    """Generate C code to parse JSON parameters"""
    if not params:
        return ""
    
    lines = []
    lines.append("        // Parse JSON parameters")
    lines.append("        if (req.content_length > 0 && strlen(req.body) > 0) {")
    
    for param in params:
        param_name = param['name']
        param_type = param['type']
        
        if param_type == 'int':
            lines.append(f'            char* {param_name}_str = strstr(req.body, "\\"{param_name}\\":");')
            lines.append(f'            int {param_name} = 0;')
            lines.append(f'            if ({param_name}_str) {{')
            lines.append(f'                {param_name}_str = strchr({param_name}_str, \':\');')
            lines.append(f'                if ({param_name}_str) {{')
            lines.append(f'                    {param_name}_str++;')
            lines.append(f'                    while (*{param_name}_str == \' \' || *{param_name}_str == \'\\t\') {param_name}_str++;')
            lines.append(f'                    {param_name} = atoi({param_name}_str);')
            lines.append(f'                }}')
            lines.append(f'            }}')
        elif param_type == 'string':
            lines.append(f'            char {param_name}[256] = "";')
            lines.append(f'            char* {param_name}_start = strstr(req.body, "\\"{param_name}\\":");')
            lines.append(f'            if ({param_name}_start) {{')
            lines.append(f'                {param_name}_start = strchr({param_name}_start, \':\');')
            lines.append(f'                if ({param_name}_start) {{')
            lines.append(f'                    {param_name}_start++;')
            lines.append(f'                    while (*{param_name}_start == \' \' || *{param_name}_start == \'\\t\') {param_name}_start++;')
            lines.append(f'                    if (*{param_name}_start == \'"\') {{')
            lines.append(f'                        {param_name}_start++;')
            lines.append(f'                        char* {param_name}_end = strchr({param_name}_start, \'"\');')
            lines.append(f'                        if ({param_name}_end) {{')
            lines.append(f'                            int len = {param_name}_end - {param_name}_start;')
            lines.append(f'                            if (len < 255) {{')
            lines.append(f'                                memcpy({param_name}, {param_name}_start, len);')
            lines.append(f'                                {param_name}[len] = 0;')
            lines.append(f'                            }}')
            lines.append(f'                        }}')
            lines.append(f'                    }}')
            lines.append(f'                }}')
            lines.append(f'            }}')
    
    lines.append("        }")
    return '\n'.join(lines)

def generate_statement_c(stmt):
    """Generate C code for a statement"""
    lines = []
    if stmt['type'] == 'assign':
        lines.append(f'            {stmt["name"]} = {expr_to_c(stmt["expr"])};')
    elif stmt['type'] == 'call' and stmt['func'] == 'add':
        lines.append(f'            {stmt["name"]}[{stmt["name"]}_len++] = {expr_to_c(stmt["arg"])};')
    elif stmt['type'] == 'return':
        lines.append(f'            {return_parts_to_c(stmt["parts"])}')
        lines.append('            send_response(client, resp, "application/json", 200);')
        lines.append('            closesocket(client);')
        lines.append('            continue;')
    elif stmt['type'] == 'if':
        lines.append(f'            if ({condition_to_c(stmt["condition"])}) {{')
        for then_stmt in stmt['then']:
            then_lines = generate_statement_c(then_stmt)
            for line in then_lines:
                lines.append('    ' + line)  # Add extra indentation
        lines.append('            }')
        if stmt['else']:
            lines.append('            else {')
            for else_stmt in stmt['else']:
                else_lines = generate_statement_c(else_stmt)
                for line in else_lines:
                    lines.append('    ' + line)  # Add extra indentation
            lines.append('            }')
    return lines

def gen_c_code(api_nodes):
    lines = []
    lines.append(r'''#pragma comment(lib, "ws2_32.lib")
#include <stdio.h>
#include <string.h>
#include <winsock2.h>
#include <ctype.h>
#include <stdlib.h>

typedef struct {
    char method[8];
    char path[256];
    int content_length;
    char body[2048];
    char content_type[128];
} HttpRequest;

void send_response(SOCKET client, const char* content, const char* content_type, int status) {
    char response[4096];
    const char* status_text = status == 200 ? "200 OK" : (status == 404 ? "404 Not Found" : "400 Bad Request");
    sprintf(response, 
        "HTTP/1.1 %s\r\n"
        "Content-Type: %s\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "Access-Control-Allow-Methods: GET, POST, PUT, DELETE\r\n"
        "Access-Control-Allow-Headers: Content-Type\r\n"
        "\r\n"
        "%s", 
        status_text, content_type, (int)strlen(content), content);
    send(client, response, (int)strlen(response), 0);
}

int parse_request(char* req, HttpRequest* out) {
    char method[8], path[256];
    int ret = sscanf(req, "%s %s", method, path);
    if(ret != 2) return 0;
    strcpy(out->method, method);
    strcpy(out->path, path);
    out->content_length = 0;
    out->body[0] = 0;
    out->content_type[0] = 0;

    char *cl = strstr(req, "Content-Length:");
    if(cl) {
        cl += 15;
        while(*cl == ' ') cl++;
        out->content_length = atoi(cl);
    }
    char *ct = strstr(req, "Content-Type:");
    if(ct) {
        ct += 13;
        while(*ct == ' ') ct++;
        int i=0;
        while(*ct && *ct!='\r' && *ct!='\n' && i<127) out->content_type[i++] = *ct++;
        out->content_type[i]=0;
    }
    char *body_start = strstr(req, "\r\n\r\n");
    if(body_start) {
        body_start += 4;
        if(out->content_length > 0) {
            memcpy(out->body, body_start, out->content_length);
            out->body[out->content_length] = 0;
        }
    }
    return 1;
}
''')

    # Global variables
    for api in api_nodes:
        for var in api.get('globals', []):
            if var['vartype'] == 'int':
                if var.get('value'):
                    lines.append(f"int {var['name']} = {expr_to_c(var['value'])};")
                else:
                    lines.append(f"int {var['name']} = 0;")
            elif var['vartype'] == 'string':
                if var.get('value'):
                    lines.append(f"char {var['name']}[256] = {expr_to_c(var['value'])};")
                else:
                    lines.append(f"char {var['name']}[256] = \"\";")
            elif var['vartype'] == 'list':
                if var['subtype'] == 'int':
                    lines.append(f"int {var['name']}[100]; int {var['name']}_len = 0;")
                elif var['subtype'] == 'string':
                    lines.append(f"char {var['name']}[100][256]; int {var['name']}_len = 0;")

    lines.append('')
    lines.append('int main() {')
    lines.append(r'''    WSADATA wsa;
    SOCKET server, client;
    struct sockaddr_in server_addr, client_addr;
    int c, recv_size;
    char client_request[4096];
    char resp[2048];

    printf("API server starting...\n");
    if (WSAStartup(MAKEWORD(2,2), &wsa) != 0) {
        printf("WSAStartup failed\n");
        return 1;
    }
    if ((server = socket(AF_INET , SOCK_STREAM , 0 )) == INVALID_SOCKET) {
        printf("Socket creation failed\n");
        return 1;
    }
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(8080);
    if (bind(server ,(struct sockaddr *)&server_addr , sizeof(server_addr)) == SOCKET_ERROR) {
        printf("Bind failed\n");
        return 1;
    }
    listen(server , 3);
    printf("Server listening on port 8080...\n");
    c = sizeof(struct sockaddr_in);''')

    # Add initialization statements
    for api in api_nodes:
        for stmt in api.get('inits', []):
            if stmt['type'] == 'call' and stmt['func'] == 'add':
                lines.append(f'    {stmt["name"]}[{stmt["name"]}_len++] = {expr_to_c(stmt["arg"])};')
            elif stmt['type'] == 'assign':
                lines.append(f'    {stmt["name"]} = {expr_to_c(stmt["expr"])};')
        # 'noop' için hiçbir şey ekleme

    lines.append('')
    lines.append(r'''    while((client = accept(server , (struct sockaddr *)&client_addr, &c)) != INVALID_SOCKET) {
        recv_size = recv(client , client_request , sizeof(client_request)-1 , 0);
        if (recv_size == SOCKET_ERROR || recv_size == 0) {
            closesocket(client);
            continue;
        }
        client_request[recv_size] = 0;

        HttpRequest req;
        if (!parse_request(client_request, &req)) {
            closesocket(client);
            continue;
        }

        printf("Request: %s %s\n", req.method, req.path);
''')

    # Routes
    for api in api_nodes:
        for route in api['routes']:
            lines.append(f'        // {route["method"]} {route["path"]}')
            lines.append(f'        if(strcmp(req.method, "{route["method"]}") == 0 && strcmp(req.path, "{route["path"]}") == 0) {{')
            
            # Add JSON parameter parsing
            if route.get('params'):
                json_parser = generate_json_parser(route['params'])
                lines.append(json_parser)
            
            # Add route body statements
            for stmt in route['body']:
                stmt_lines = generate_statement_c(stmt)
                lines.extend(stmt_lines)
            
            lines.append('        }')

    lines.append(r'''        // Default 404 response
        send_response(client, "{\"error\":\"404 Not Found\"}", "application/json", 404);
        closesocket(client);
    }
    closesocket(server);
    WSACleanup();
    return 0;
}''')
    return '\n'.join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <file.gcode> [--run]")
        return

    filename = sys.argv[1]
    run_after = '--run' in sys.argv

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: File {filename} not found")
        return

    tokens = tokenize(code)
    parser = Parser(tokens)
    try:
        api_nodes = parser.parse()
        if not api_nodes:
            print("Error: No API definition found")
            return
    except Exception as e:
        print(f"Parsing error: {e}")
        return

    c_code = gen_c_code(api_nodes)

    c_file = 'output.c'
    with open(c_file, 'w', encoding='utf-8') as f:
        f.write(c_code)

    print("Compiling...")
    # Try different compiler commands
    compilers = [
        ['gcc', c_file, '-o', 'output.exe', '-lws2_32'],
        ['gcc', c_file, '-o', 'output', '-lws2_32'],
        ['clang', c_file, '-o', 'output.exe', '-lws2_32'],
        ['cl', c_file, '/Fe:output.exe', 'ws2_32.lib']
    ]
    
    compiled = False
    for gcc_cmd in compilers:
        try:
            proc = subprocess.run(gcc_cmd, capture_output=True, timeout=30)
            if proc.returncode == 0:
                print(f"Compilation successful with: {' '.join(gcc_cmd)}")
                compiled = True
                break
            else:
                continue
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    
    if not compiled:
        print("Compilation failed. Make sure you have GCC or another C compiler installed.")
        print("On Windows, you may need to install MinGW-w64 or Visual Studio.")
        return

    executable = 'output.exe' if os.name == 'nt' else './output'
    
    if run_after:
        print("Starting server...")
        try:
            subprocess.run([executable])
        except KeyboardInterrupt:
            print("\nServer stopped.")
        except FileNotFoundError:
            print(f"Error: Could not find executable {executable}")

if __name__ == "__main__":
    main()