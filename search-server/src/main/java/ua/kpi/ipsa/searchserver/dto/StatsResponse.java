package ua.kpi.ipsa.searchserver.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record StatsResponse(
        int documents,
        @JsonProperty("index_build_time_ms") long indexBuildTimeMs,
        @JsonProperty("threads_used") int threadsUsed
) {
}