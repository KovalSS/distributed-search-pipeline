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
        String prompt = "Given this search query, provide 3-5 related keywords or synonyms, "
                + "separated by commas only, no explanations, no numbering. Query: \"" + query + "\"";

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

    private List<String> parseTerms(String rawResponse) {
        List<String> terms = new ArrayList<>();
        String[] parts = rawResponse.split(",");
        for (String part : parts) {
            String cleaned = part.trim().toLowerCase();
            if (!cleaned.isBlank()) {
                terms.add(cleaned);
            }
        }
        return terms;
    }
}