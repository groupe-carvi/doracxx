#pragma once

#include <arrow/api.h>
#include <arrow/compute/api.h>
#include <dora-node-api.h>
#include <memory>
#include <vector>
#include <optional>

/**
 * Arrow-enabled Dora node processor
 * 
 * This class demonstrates how to use Apache Arrow with Dora nodes
 * for efficient data processing and zero-copy operations.
 */
class ArrowProcessor {
public:
    ArrowProcessor();
    ~ArrowProcessor();
    
    /**
     * Process input data using Arrow arrays
     * @param input Raw input data
     * @param output Processed output data
     * @return Status of the operation
     */
    std::optional<std::vector<uint8_t>> process_with_arrow(
        const std::vector<uint8_t>& input);
    
    /**
     * Create an Arrow array from input data
     * @param data Input data vector
     * @return Arrow array or error
     */
    arrow::Result<std::shared_ptr<arrow::Array>> create_arrow_array(
        const std::vector<double>& data);
    
    /**
     * Perform computation on Arrow array
     * @param array Input Arrow array
     * @return Computed result
     */
    arrow::Result<std::shared_ptr<arrow::Array>> compute_sum(
        const std::shared_ptr<arrow::Array>& array);
    
private:
    std::shared_ptr<arrow::MemoryPool> memory_pool_;
};
