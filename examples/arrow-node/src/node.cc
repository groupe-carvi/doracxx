#include "arrow_processor.h"
#include <arrow/array.h>
#include <arrow/builder.h>
#include <arrow/compute/exec.h>
#include <arrow/memory_pool.h>
#include <iostream>

// Include Dora headers
#include "dora-node-api.h"

int main() {
    std::cout << "[INFO] Starting Arrow-enabled Dora node" << std::endl;
    
    // Initialize Arrow processor
    ArrowProcessor processor;
    
    // Initialize Dora node
    auto dora_node = init_dora_node();
    
    for (int i = 0; i < 100; i++) {
        auto event = dora_node.events->next();
        auto ty = event_type(event);

        if (ty == DoraEventType::AllInputsClosed) {
            std::cout << "[INFO] All inputs closed, exiting" << std::endl;
            break;
        }
        else if (ty == DoraEventType::Input) {
            auto input = event_as_input(std::move(event));
            
            std::cout << "[PROCESS] Processing input with Arrow: " << std::string(input.id) << std::endl;
            
            // Convert input data to vector
            std::vector<uint8_t> input_data;
            for (auto byte : input.data) {
                input_data.push_back(byte);
            }
            
            // Process with Arrow
            auto result = processor.process_with_arrow(input_data);
            if (!result.has_value()) {
                std::cerr << "[ERROR] Arrow processing failed" << std::endl;
                continue;
            }
            
            // Send output
            const auto& output_data = result.value();
            ::rust::Slice<const uint8_t> data_slice{output_data.data(), output_data.size()};
            auto send_result = send_output(dora_node.send_output, "arrow_output", data_slice);
            if (!std::string(send_result.error).empty()) {
                std::cerr << "[ERROR] Failed to send output: " << std::string(send_result.error) << std::endl;
            } else {
                std::cout << "[INFO] Successfully sent Arrow output" << std::endl;
            }
        }
        else {
            std::cerr << "[WARN] Unknown event type " << static_cast<int>(ty) << std::endl;
        }
    }
    
    std::cout << "[INFO] Arrow-enabled Dora node finished" << std::endl;
    return 0;
}

// ArrowProcessor implementation
ArrowProcessor::ArrowProcessor() 
    : memory_pool_(arrow::default_memory_pool()) {
    std::cout << "[ARROW] Initialized Arrow processor with memory pool" << std::endl;
}

ArrowProcessor::~ArrowProcessor() {
    std::cout << "[ARROW] Destroyed Arrow processor" << std::endl;
}

std::optional<std::vector<uint8_t>> ArrowProcessor::process_with_arrow(
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
            std::cerr << "[ERROR] Failed to create Arrow array: " << array_result.status().ToString() << std::endl;
            return std::nullopt;
        }
        auto array = array_result.ValueOrDie();
        
        std::cout << "[ARROW] Created array with " << array->length() << " elements" << std::endl;
        
        // Perform computation
        auto sum_result = compute_sum(array);
        if (!sum_result.ok()) {
            std::cerr << "[ERROR] Failed to compute sum: " << sum_result.status().ToString() << std::endl;
            return std::nullopt;
        }
        auto sum_array = sum_result.ValueOrDie();
        
        // Convert result back to bytes
        auto double_array = std::static_pointer_cast<arrow::DoubleArray>(sum_array);
        double sum_value = double_array->Value(0);
        
        std::cout << "[ARROW] Computed sum: " << sum_value << std::endl;
        
        // Convert result to output bytes
        std::vector<uint8_t> output_data(sizeof(double));
        std::memcpy(output_data.data(), &sum_value, sizeof(double));
        
        return output_data;
        
    } catch (const std::exception& e) {
        std::cerr << "[ERROR] Arrow processing exception: " << e.what() << std::endl;
        return std::nullopt;
    }
}

arrow::Result<std::shared_ptr<arrow::Array>> ArrowProcessor::create_arrow_array(
    const std::vector<double>& data) {
    
    arrow::DoubleBuilder builder(arrow::default_memory_pool());
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
    ExecContext exec_context(arrow::default_memory_pool());
    
    // Compute sum using proper API
    ARROW_ASSIGN_OR_RAISE(arrow::Datum sum_datum, Sum(array, ScalarAggregateOptions::Defaults(), &exec_context));
    
    return sum_datum.make_array();
}
