package ua.kpi.ipsa.searchserver.index;

import java.util.List;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record ProductDocument(
        String title,
        List<String> features,
        List<String> description,
        String store,
        String parent_asin
) {
}