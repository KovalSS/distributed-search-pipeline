package ua.kpi.ipsa.searchserver.dto;

public record SearchRequest(String query, String mode, Integer top) {
}