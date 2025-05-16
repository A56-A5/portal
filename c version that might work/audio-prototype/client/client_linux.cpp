#include <iostream>
#include <cstdlib>
#include <cstring>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>

#define PORT 50007
#define CHUNK_SIZE 4096

int main() {
    const char* server_ip = getenv("SERVER_IP");
    if (!server_ip) server_ip = "127.0.0.1";

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in server_addr {};
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(PORT);
    inet_pton(AF_INET, server_ip, &server_addr.sin_addr);

    connect(sock, (sockaddr*)&server_addr, sizeof(server_addr));
    std::cout << "Connected to server.\n";

    FILE* pipe = popen("parec --format=s16le --rate=44100 --channels=1", "r");
    char buffer[CHUNK_SIZE];

    while (!feof(pipe)) {
        size_t read = fread(buffer, 1, CHUNK_SIZE, pipe);
        if (read > 0) send(sock, buffer, read, 0);
    }

    pclose(pipe);
    close(sock);
    return 0;
}
