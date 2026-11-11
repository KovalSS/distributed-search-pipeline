package ua.kpi.ipsa.searchserver.index;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
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

    public record DocLocation(short fileIndex, long byteOffset, int length) {
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
            try (FileChannel channel = FileChannel.open(file, StandardOpenOption.READ)) {
                ByteBuffer buffer = ByteBuffer.allocate(64 * 1024);
                byte[] lineBuffer = new byte[8192];
                int lineLen = 0;
                long currentPos = 0;
                long lineStartOffset = 0;

                while (channel.read(buffer) > 0) {
                    buffer.flip();
                    while (buffer.hasRemaining()) {
                        byte b = buffer.get();
                        currentPos++;
                        if (b == '\n') {
                            int textLen = lineLen;
                            if (textLen > 0 && lineBuffer[textLen - 1] == '\r') {
                                textLen--;
                            }
                            if (textLen > 0) {
                                String line = new String(lineBuffer, 0, textLen, StandardCharsets.UTF_8);
                                if (!line.isBlank()) {
                                    try {
                                        ProductDocument product = objectMapper.readValue(line, ProductDocument.class);
                                        String docId = product.parent_asin();
                                        String text = buildIndexableText(product);

                                        if (docId != null && !text.isBlank()) {
                                            targetIndex.addDocument(docId, text);
                                            if (product.title() != null) {
                                                targetTitles.put(docId, product.title());
                                            }
                                            int lineLength = (int) (currentPos - lineStartOffset);
                                            targetLocations.put(docId, new DocLocation(fileIdx, lineStartOffset, lineLength));
                                            counter.incrementAndGet();
                                        }
                                    } catch (Exception e) {
                                        System.err.println("Failed to parse line in " + file + ": " + e.getMessage());
                                    }
                                }
                            }
                            lineLen = 0;
                            lineStartOffset = currentPos;
                        } else {
                            if (lineLen >= lineBuffer.length) {
                                lineBuffer = Arrays.copyOf(lineBuffer, lineBuffer.length * 2);
                            }
                            lineBuffer[lineLen++] = b;
                        }
                    }
                    buffer.clear();
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
        int total = files.size();
        if (total == 0 || chunkCount <= 0) {
            return chunks;
        }

        int baseSize = total / chunkCount;
        int remainder = total % chunkCount;

        int startIndex = 0;
        for (int i = 0; i < chunkCount; i++) {
            int currentChunkSize = baseSize + (i < remainder ? 1 : 0);
            if (currentChunkSize > 0) {
                chunks.add(files.subList(startIndex, startIndex + currentChunkSize));
                startIndex += currentChunkSize;
            }
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
        try (FileChannel channel = FileChannel.open(file, StandardOpenOption.READ)) {
            ByteBuffer dst = ByteBuffer.allocate(loc.length());
            channel.position(loc.byteOffset());
            channel.read(dst);
            dst.flip();
            return StandardCharsets.UTF_8.decode(dst).toString().trim();
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
