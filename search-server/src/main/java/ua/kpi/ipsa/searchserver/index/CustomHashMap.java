package ua.kpi.ipsa.searchserver.index;

import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReferenceArray;
import java.util.concurrent.locks.ReentrantLock;

public class CustomHashMap<K> {

    private static final int BUCKET_COUNT = 1 << 20;

    private static class Entry<K> {
        final K key;
        final ConcurrentPostingList value;
        final Entry<K> next;

        Entry(K key, ConcurrentPostingList value, Entry<K> next) {
            this.key = key;
            this.value = value;
            this.next = next;
        }
    }

    private final AtomicReferenceArray<Entry<K>> buckets = new AtomicReferenceArray<>(BUCKET_COUNT);
    private final ReentrantLock[] bucketLocks = new ReentrantLock[BUCKET_COUNT];
    private final AtomicInteger keyCount = new AtomicInteger(0);

    public CustomHashMap() {
        for (int i = 0; i < BUCKET_COUNT; i++) {
            bucketLocks[i] = new ReentrantLock();
        }
    }

    private int bucketIndex(K key) {
        int h = key.hashCode();
        h ^= (h >>> 16);
        return h & (BUCKET_COUNT - 1);
    }

    public ConcurrentPostingList getOrCreate(K key) {
        int idx = bucketIndex(key);

        Entry<K> existing = findInBucket(buckets.get(idx), key);
        if (existing != null) {
            return existing.value;
        }

        ReentrantLock lock = bucketLocks[idx];
        lock.lock();
        try {
            existing = findInBucket(buckets.get(idx), key);
            if (existing != null) {
                return existing.value;
            }
            ConcurrentPostingList newList = new ConcurrentPostingList();
            Entry<K> newEntry = new Entry<>(key, newList, buckets.get(idx));
            buckets.set(idx, newEntry);
            keyCount.incrementAndGet();
            return newList;
        } finally {
            lock.unlock();
        }
    }

    public ConcurrentPostingList get(K key) {
        Entry<K> found = findInBucket(buckets.get(bucketIndex(key)), key);
        return found != null ? found.value : null;
    }

    private Entry<K> findInBucket(Entry<K> head, K key) {
        Entry<K> current = head;
        while (current != null) {
            if (current.key.equals(key)) {
                return current;
            }
            current = current.next;
        }
        return null;
    }

    public int size() {
        return keyCount.get();
    }
}