#include <Eigen/Dense>
#include <iostream>

int main() {
    std::cout << "Testing Eigen3..." << std::endl;
    
    // Create a 3x3 matrix
    Eigen::Matrix3d matrix;
    matrix << 1, 2, 3,
              4, 5, 6,
              7, 8, 9;
    
    std::cout << "Matrix:\n" << matrix << std::endl;
    
    // Compute determinant
    double det = matrix.determinant();
    std::cout << "Determinant: " << det << std::endl;
    
    // Create a vector
    Eigen::Vector3d vector(1, 2, 3);
    std::cout << "Vector: " << vector.transpose() << std::endl;
    
    // Matrix-vector multiplication
    Eigen::Vector3d result = matrix * vector;
    std::cout << "Matrix * Vector: " << result.transpose() << std::endl;
    
    std::cout << "Eigen3 test completed successfully!" << std::endl;
    return 0;
}
