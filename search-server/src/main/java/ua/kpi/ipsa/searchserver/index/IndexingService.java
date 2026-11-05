package ua.kpi.ipsa.searchserver.index;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
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

    public record DocLocation(short fileIndex, int lineIndex) {
    }

    private volatile InvertedIndex index = new InvertedIndex();
    private volatile ConcurrentHashMap<String, String> docTitles = new ConcurrentHashMap<>();
    private volatile ConcurrentHashMap<String, DocLocation> docLocations = new ConcurrentHashMap<>();
    private volatile List<Path> datasetFiles = new ArrayList<>();
    private final ObjectMapper objectMapper = new ObjectMapper();

    private volatile int documentsIndexed = 0;
    private volatile long lastBuildTimeMs = 0;
    private volatile int lastThreadsUsed = 0;

    public synchronized IndexResult buildIndex(int threadCount) {
        this.index = new InvertedIndex();
        this.docTitles = new ConcurrentHashMap<>();
        this.docLocations = new ConcurrentHashMap<>();
        this.datasetFiles = new ArrayList<>();
        System.gc();

        InvertedIndex newIndex = new InvertedIndex();
        ConcurrentHashMap<String, String> newTitles = new ConcurrentHashMap<>();
        ConcurrentHashMap<String, DocLocation> newLocations = new ConcurrentHashMap<>();

        List<Path> files = listDatasetFiles();
        Map<Path, Short> fileIndexMap = new HashMap<>();
        for (short i = 0; i < files.size(); i++) {
            fileIndexMap.put(files.get(i), i);
        }

        ThreadPool pool = new ThreadPool(threadCount);
        AtomicInteger indexedCounter = new AtomicInteger(0);

        List<List<Path>> chunks = splitIntoChunks(files, threadCount);

        long start = System.currentTimeMillis();

        for (List<Path> chunk : chunks) {
            pool.submit(() -> indexChunk(chunk, fileIndexMap, newIndex, newTitles, newLocations, indexedCounter));
        }

        pool.awaitCompletion();
        pool.shutdown();

        long elapsed = System.currentTimeMillis() - start;

        index = newIndex;
        docTitles = newTitles;
        docLocations = newLocations;
        datasetFiles = files;
        documentsIndexed = indexedCounter.get();
        lastBuildTimeMs = elapsed;
        lastThreadsUsed = threadCount;

        return new IndexResult(documentsIndexed, elapsed);
    }

    private void indexChunk(List<Path> chunk, Map<Path, Short> fileIndexMap, InvertedIndex targetIndex,
            ConcurrentHashMap<String, String> targetTitles,
            ConcurrentHashMap<String, DocLocation> targetLocations, AtomicInteger counter) {
        for (Path file : chunk) {
            short fileIdx = fileIndexMap.getOrDefault(file, (short) 0);
            try (BufferedReader reader = Files.newBufferedReader(file)) {
                String line;
                int lineIdx = 0;
                while ((line = reader.readLine()) != null) {
                    if (line.isBlank()) {
                        lineIdx++;
                        continue;
                    }
                    try {
                        ProductDocument product = objectMapper.readValue(line, ProductDocument.class);
                        String docId = product.parent_asin();
                        String text = buildIndexableText(product);

                        if (docId != null && !text.isBlank()) {
                            targetIndex.addDocument(docId, text);
                            if (product.title() != null) {
                                targetTitles.put(docId, product.title());
                            }
                            targetLocations.put(docId, new DocLocation(fileIdx, lineIdx));
                            counter.incrementAndGet();
                        }
                    } catch (Exception e) {
                        System.err.println("Failed to parse line in " + file + ": " + e.getMessage());
                    }
                    lineIdx++;
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

    public String getTitle(String docId) {
        return docTitles.getOrDefault(docId, "");
    }

    public String getRawDocumentJson(String docId) {
        if (docId == null || docLocations == null || datasetFiles == null) {
            return null;
        }
        DocLocation loc = docLocations.get(docId);
        if (loc == null || loc.fileIndex() < 0 || loc.fileIndex() >= datasetFiles.size()) {
            return null;
        }
        Path file = datasetFiles.get(loc.fileIndex());
        try (Stream<String> lines = Files.lines(file)) {
            return lines.skip(loc.lineIndex()).findFirst().orElse(null);
        } catch (IOException e) {
            return null;
        }
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
