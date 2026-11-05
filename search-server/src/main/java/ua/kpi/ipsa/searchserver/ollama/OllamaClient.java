package ua.kpi.ipsa.searchserver.ollama;

import java.util.ArrayList;
import java.util.List;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

@Service
public class OllamaClient {

    @Value("${ollama.base-url}")
    private String baseUrl;

    @Value("${ollama.model}")
    private String model;

    private RestClient restClient;

    private RestClient client() {
        if (restClient == null) {
            restClient = RestClient.create(baseUrl);
        }
        return restClient;
    }

    public boolean isAvailable() {
        try {
            client().get()
                    .uri("/api/tags")
                    .retrieve()
                    .toBodilessEntity();
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    public List<String> expandQuery(String query) {
        String prompt = """
                <|start_header_id|>system<|end_header_id|>
                You are a shopping search query expansion engine. For the given product query, provide 3 to 5 close product synonyms or alternative shopping terms for the exact same item.
                Output ONLY a single comma-separated list of terms. Do NOT include explanations, introductory words, or punctuation marks.<|eot_id|>
                <|start_header_id|>user<|end_header_id|>
                Product query: "%s"<|eot_id|>
                <|start_header_id|>assistant<|end_header_id|>
                """.formatted(query);

        OllamaGenerateRequest request = new OllamaGenerateRequest(model, prompt, false);

        try {
            OllamaGenerateResponse response = client().post()
                    .uri("/api/generate")
                    .body(request)
                    .retrieve()
                    .body(OllamaGenerateResponse.class);

            if (response == null || response.response() == null) {
                return List.of();
            }

            return parseTerms(response.response());
        } catch (Exception e) {
            System.err.println("Ollama query expansion failed: " + e.getMessage());
            return List.of();
        }
    }

    List<String> parseTerms(String rawResponse) {
        List<String> terms = new ArrayList<>();
        String text = rawResponse.replace("\n", ",");
        int colonIdx = text.indexOf(':');
        if (colonIdx != -1 && (text.indexOf(',') == -1 || colonIdx < text.indexOf(','))) {
            text = text.substring(colonIdx + 1);
        }

        String[] parts = text.contains(",") ? text.split(",") : text.split("\\s+");
        for (String part : parts) {
            String cleaned = part.trim().toLowerCase().replaceAll("^[\\\"'\\-\\d.]+|[\\\"'.]+$", "").trim();
            if (!cleaned.isBlank() && cleaned.split("\\s+").length <= 4 && !terms.contains(cleaned)) {
                terms.add(cleaned);
            }
        }
        return terms;
    }
}
