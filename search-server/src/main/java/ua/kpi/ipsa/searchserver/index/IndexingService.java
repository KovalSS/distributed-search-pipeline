package ua.kpi.ipsa.searchserver.index;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import tools.jackson.databind.ObjectMapper;

import ua.kpi.ipsa.searchserver.threadpool.ThreadPool;

@Service
public class IndexingService {

    @Value("${search.dataset.path}")
    private String datasetPath;

    private volatile InvertedIndex index = new InvertedIndex();
    private final ObjectMapper objectMapper = new ObjectMapper();

    private volatile int documentsIndexed = 0;
    private volatile long lastBuildTimeMs = 0;
    private volatile int lastThreadsUsed = 0;

    public IndexResult buildIndex(int threadCount) {
        InvertedIndex newIndex = new InvertedIndex();

        List<Path> files = listDatasetFiles();
        ThreadPool pool = new ThreadPool(threadCount);
        AtomicInteger indexedCounter = new AtomicInteger(0);

        List<List<Path>> chunks = splitIntoChunks(files, threadCount);

        long start = System.currentTimeMillis();

        for (List<Path> chunk : chunks) {
            pool.submit(() -> indexChunk(chunk, newIndex, indexedCounter));
        }

        pool.awaitCompletion();
        pool.shutdown();

        long elapsed = System.currentTimeMillis() - start;

        index = newIndex;
        documentsIndexed = indexedCounter.get();
        lastBuildTimeMs = elapsed;
        lastThreadsUsed = threadCount;

        return new IndexResult(documentsIndexed, elapsed);
    }

    private void indexChunk(List<Path> chunk, InvertedIndex targetIndex, AtomicInteger counter) {
        for (Path file : chunk) {
            try (BufferedReader reader = Files.newBufferedReader(file)) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.isBlank()) {
                        continue;
                    }
                    try {
                        ProductDocument product = objectMapper.readValue(line, ProductDocument.class);
                        String docId = product.parent_asin();
                        String text = buildIndexableText(product);

                        if (docId != null && !text.isBlank()) {
                            targetIndex.addDocument(docId, text);
                            counter.incrementAndGet();
                        }
                    } catch (Exception e) {
                        System.err.println("Failed to parse line in " + file + ": " + e.getMessage());
                    }
                }
            } catch (IOException e) {
                System.err.println("Failed to read file: " + file + " — " + e.getMessage());
            }
        }
    }

    private String buildIndexableText(ProductDocument product) {
        StringBuilder sb = new StringBuilder();

        if (product.title() != null) {
            sb.append(product.title()).append(" ");
        }
        if (product.features() != null) {
            product.features().forEach(f -> sb.append(f).append(" "));
        }
        if (product.description() != null) {
            product.description().forEach(d -> sb.append(d).append(" "));
        }
        if (product.store() != null) {
            sb.append(product.store());
        }
        return sb.toString();
    }

    private List<Path> listDatasetFiles() {
        try (Stream<Path> stream = Files.list(Path.of(datasetPath))) {
            return stream
                    .filter(Files::isRegularFile)
                    .collect(Collectors.toList());
        } catch (IOException e) {
            throw new RuntimeException("Failed to read dataset directory: " + datasetPath, e);
        }
    }

    private List<List<Path>> splitIntoChunks(List<Path> files, int chunkCount) {
        List<List<Path>> chunks = new java.util.ArrayList<>();
        int chunkSize = (int) Math.ceil((double) files.size() / chunkCount);

        for (int i = 0; i < files.size(); i += chunkSize) {
            chunks.add(files.subList(i, Math.min(i + chunkSize, files.size())));
        }
        return chunks;
    }

    public InvertedIndex getIndex() {
        return index;
    }

    public int getDocumentsIndexed() {
        return documentsIndexed;
    }

    public long getLastBuildTimeMs() {
        return lastBuildTimeMs;
    }

    public int getLastThreadsUsed() {
        return lastThreadsUsed;
    }

    public record IndexResult(int documentsIndexed, long timeMs) {
    }
}