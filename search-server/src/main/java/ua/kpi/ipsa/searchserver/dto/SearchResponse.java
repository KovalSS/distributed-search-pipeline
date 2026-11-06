package ua.kpi.ipsa.searchserver.dto;

import java.util.List;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

public record SearchResponse(
        List<SearchResult> results,
        @JsonProperty("time_ms") long timeMs,
        @JsonInclude(JsonInclude.Include.NON_NULL) List<String> synonyms
) {

    public SearchResponse(List<SearchResult> results, long timeMs) {
        this(results, timeMs, null);
    }

    public record SearchResult(
            @JsonProperty("doc_id") String docId,
            double score,
            String snippet,
            @JsonInclude(JsonInclude.Include.NON_NULL) Object raw
    ) {
    }
}
