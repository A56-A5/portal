// Compile with: g++ audio_server.cpp -lpulse-simple -lpulse -o audio_server
#include <iostream>
#include <unistd.h>
#include <netinet/in.h>
#include <pulse/simple.h>
#include <pulse/error.h>

#define PORT 5000
#define BUF_SIZE 4096

int main() {
    // Set up PulseAudio playback
    static const pa_sample_spec ss = {
        .format = PA_SAMPLE_S16LE, // 16-bit little endian
        .rate = 48000,
        .channels = 2
    };

    int error;
    pa_simple *s = pa_simple_new(nullptr, "AudioServer", PA_STREAM_PLAYBACK, nullptr, "playback", &ss, nullptr, nullptr, &error);
    if (!s) {
        std::cerr << "PulseAudio error: " << pa_strerror(error) << "\n";
        return 1;
    }

    // TCP socket setup
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(PORT);
    addr.sin_addr.s_addr = INADDR_ANY;

    bind(server_fd, (struct sockaddr*)&addr, sizeof(addr));
    listen(server_fd, 1);
    std::cout << "Waiting for connection on port " << PORT << "...\n";

    int client_fd = accept(server_fd, nullptr, nullptr);
    std::cout << "Client connected.\n";

    // Read and play audio
    char buffer[BUF_SIZE];
    while (true) {
        ssize_t bytes = read(client_fd, buffer, BUF_SIZE);
        if (bytes <= 0) break;

        if (pa_simple_write(s, buffer, (size_t)bytes, &error) < 0) {
            std::cerr << "PulseAudio write error: " << pa_strerror(error) << "\n";
            break;
        }
    }

    pa_simple_drain(s, &error);
    pa_simple_free(s);
    close(client_fd);
    close(server_fd);
    std::cout << "Connection closed.\n";
    return 0;
}
