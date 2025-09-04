#include "arrow_processor.h"
#include <arrow/array.h>
#include <arrow/builder.h>
#include <arrow/compute/exec.h>
#include <arrow/memory_pool.h>
#include <iostream>

// Main Dora node implementation
extern "C" {

dora::Result<void> dora_init() {
    std::cout << "[INFO] Initializing Arrow-enabled Dora node" << std::endl;
    return {};
}

dora::Result<void> dora_process(const dora::Input& input, dora::Output& output) {
    static ArrowProcessor processor;
    
    std::cout << "[PROCESS] Processing input with Arrow: " << input.id << std::endl;
    
    // Convert input data to vector
    std::vector<uint8_t> input_data(input.data, input.data + input.len);
    
    // Process with Arrow
    auto result = processor.process_with_arrow(input_data);
    if (!result.has_value()) {
        std::cerr << "[ERROR] Arrow processing failed" << std::endl;
        return result.error();
    }
    
    // Send output
    const auto& output_data = result.value();
    output.send_data("arrow_output", output_data.data(), output_data.size());
    
    return {};
}

dora::Result<void> dora_destroy() {
    std::cout << "[INFO] Destroying Arrow-enabled Dora node" << std::endl;
    return {};
}

} // extern "C"

// ArrowProcessor implementation
ArrowProcessor::ArrowProcessor() 
    : memory_pool_(arrow::default_memory_pool()) {
    std::cout << "[ARROW] Initialized Arrow processor with memory pool" << std::endl;
}

ArrowProcessor::~ArrowProcessor() {
    std::cout << "[ARROW] Destroyed Arrow processor" << std::endl;
}

dora::Result<std::vector<uint8_t>> ArrowProcessor::process_with_arrow(
    const std::vector<uint8_t>& input) {
    
    try {
        // Convert raw bytes to doubles for demonstration
        std::vector<double> values;
        for (size_t i = 0; i < input.size(); i += sizeof(double)) {
            if (i + sizeof(double) <= input.size()) {
                double value;
                std::memcpy(&value, &input[i], sizeof(double));
                values.push_back(value);
            }
        }
        
        // If no double values, create some example data
        if (values.empty()) {
            values = {1.0, 2.0, 3.0, 4.0, 5.0};
            std::cout << "[ARROW] Using example data: [1.0, 2.0, 3.0, 4.0, 5.0]" << std::endl;
        }
        
        // Create Arrow array
        auto array_result = create_arrow_array(values);
        if (!array_result.ok()) {
            return dora::Result<std::vector<uint8_t>>::error("Failed to create Arrow array");
        }
        auto array = array_result.ValueOrDie();
        
        std::cout << "[ARROW] Created array with " << array->length() << " elements" << std::endl;
        
        // Perform computation
        auto sum_result = compute_sum(array);
        if (!sum_result.ok()) {
            return dora::Result<std::vector<uint8_t>>::error("Failed to compute sum");
        }
        auto sum_array = sum_result.ValueOrDie();
        
        // Convert result back to bytes
        auto double_array = std::static_pointer_cast<arrow::DoubleArray>(sum_array);
        double sum_value = double_array->Value(0);
        
        std::cout << "[ARROW] Computed sum: " << sum_value << std::endl;
        
        // Convert result to output bytes
        std::vector<uint8_t> output_data(sizeof(double));
        std::memcpy(output_data.data(), &sum_value, sizeof(double));
        
        return dora::Result<std::vector<uint8_t>>::ok(std::move(output_data));
        
    } catch (const std::exception& e) {
        std::cerr << "[ERROR] Arrow processing exception: " << e.what() << std::endl;
        return dora::Result<std::vector<uint8_t>>::error("Arrow processing failed");
    }
}

arrow::Result<std::shared_ptr<arrow::Array>> ArrowProcessor::create_arrow_array(
    const std::vector<double>& data) {
    
    arrow::DoubleBuilder builder(memory_pool_);
    ARROW_RETURN_NOT_OK(builder.Reserve(data.size()));
    
    for (double value : data) {
        ARROW_RETURN_NOT_OK(builder.Append(value));
    }
    
    std::shared_ptr<arrow::Array> array;
    ARROW_RETURN_NOT_OK(builder.Finish(&array));
    
    return array;
}

arrow::Result<std::shared_ptr<arrow::Array>> ArrowProcessor::compute_sum(
    const std::shared_ptr<arrow::Array>& array) {
    
    using namespace arrow::compute;
    
    // Create compute context
    ExecContext exec_context(memory_pool_);
    
    // Compute sum
    ARROW_ASSIGN_OR_RAISE(Datum sum_datum, Sum(array, &exec_context));
    
    return sum_datum.make_array();
}
