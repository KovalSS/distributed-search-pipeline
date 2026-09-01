package ua.kpi.ipsa.searchserver.dto;

public record IndexResponse(String status, int documentsIndexed, long timeMs) {
}