#include "dora-node-api.h"
#include <iostream>
#include <chrono>
#include <thread>

int main() {
    std::cout << "Starting simple Dora C++ node..." << std::endl;
    
    // Simulate some work
    for (int i = 0; i < 5; ++i) {
        std::cout << "Processing iteration " << (i + 1) << "/5" << std::endl;
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
    
    std::cout << "Simple node completed successfully!" << std::endl;
    return 0;
}
