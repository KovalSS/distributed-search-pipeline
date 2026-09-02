package ua.kpi.ipsa.searchserver.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record IndexResponse(
        String status,
        @JsonProperty("documents_indexed") int documentsIndexed,
        @JsonProperty("time_ms") long timeMs
) {
}