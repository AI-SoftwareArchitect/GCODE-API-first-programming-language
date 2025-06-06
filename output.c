#pragma comment(lib, "ws2_32.lib")
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

int users[100]; int users_len = 0;
int total_added = 0;

int main() {
    WSADATA wsa;
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
    c = sizeof(struct sockaddr_in);
    users[users_len++] = 10;
    users[users_len++] = 20;

    while((client = accept(server , (struct sockaddr *)&client_addr, &c)) != INVALID_SOCKET) {
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

        // POST /add
        if(strcmp(req.method, "POST") == 0 && strcmp(req.path, "/add") == 0) {
        // Parse JSON parameters
        if (req.content_length > 0 && strlen(req.body) > 0) {
            char* newuser_str = strstr(req.body, "\"newuser\":");
            int newuser = 0;
            if (newuser_str) {
                newuser_str = strchr(newuser_str, ':');
                if (newuser_str) {
                    newuser_str++;
                    while (*newuser_str == ' ' || *newuser_str == '\t') newuser_str++;
                    newuser = atoi(newuser_str);
                }
            }
            char name[256] = "";
            char* name_start = strstr(req.body, "\"name\":");
            if (name_start) {
                name_start = strchr(name_start, ':');
                if (name_start) {
                    name_start++;
                    while (*name_start == ' ' || *name_start == '\t') name_start++;
                    if (*name_start == '"') {
                        name_start++;
                        char* name_end = strchr(name_start, '"');
                        if (name_end) {
                            int len = name_end - name_start;
                            if (len < 255) {
                                memcpy(name, name_start, len);
                                name[len] = 0;
                            }
                        }
                    }
                }
            }
        }
            users[users_len++] = newuser;
            sprintf(resp, "{\\\"success\\\": true, \\\"added\\\": %d, \\\"total\\\": %d, \\\"count\\\": %d}", users[(users_len - 1)], total_added, users_len);
            send_response(client, resp, "application/json", 200);
            closesocket(client);
            continue;
        }
        // GET /all
        if(strcmp(req.method, "GET") == 0 && strcmp(req.path, "/all") == 0) {
            sprintf(resp, "{\\\"users\\\": [%d,%d,%d,%d,%d], \\\"count\\\": %d}", users[0], users[1], users[2], users[3], users[4], users_len);
            send_response(client, resp, "application/json", 200);
            closesocket(client);
            continue;
        }
        // GET /count
        if(strcmp(req.method, "GET") == 0 && strcmp(req.path, "/count") == 0) {
            sprintf(resp, "{\\\"count\\\": %d}", users_len);
            send_response(client, resp, "application/json", 200);
            closesocket(client);
            continue;
        }
        // GET /news
        if(strcmp(req.method, "GET") == 0 && strcmp(req.path, "/news") == 0) {
            strcpy(resp, "newssssssssssssssssssssssssssss!!");
            send_response(client, resp, "application/json", 200);
            closesocket(client);
            continue;
        }
        // GET /last
        if(strcmp(req.method, "GET") == 0 && strcmp(req.path, "/last") == 0) {
            sprintf(resp, "{\\\"last\\\": %d}", users[(users_len - 1)]);
            send_response(client, resp, "application/json", 200);
            closesocket(client);
            continue;
        }
        // POST /reset
        if(strcmp(req.method, "POST") == 0 && strcmp(req.path, "/reset") == 0) {
            if (users_len > 2) {
                users_len = 2;
                total_added = 0;
                sprintf(resp, "{\\\"reset\\\": true, \\\"count\\\": %d}", users_len);
                send_response(client, resp, "application/json", 200);
                closesocket(client);
                continue;
            }
            else {
                sprintf(resp, "{\\\"reset\\\": false, \\\"count\\\": %d}", users_len);
                send_response(client, resp, "application/json", 200);
                closesocket(client);
                continue;
            }
        }
        // Default 404 response
        send_response(client, "{\"error\":\"404 Not Found\"}", "application/json", 404);
        closesocket(client);
    }
    closesocket(server);
    WSACleanup();
    return 0;
}