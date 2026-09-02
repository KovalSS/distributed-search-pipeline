package ua.kpi.ipsa.searchserver.dto;

import java.util.List;
import com.fasterxml.jackson.annotation.JsonProperty;

public record SearchResponse(List<SearchResult> results, @JsonProperty("time_ms") long timeMs) {

    public record SearchResult(
            @JsonProperty("doc_id") String docId,
            double score,
            String snippet
    ) {
    }
}