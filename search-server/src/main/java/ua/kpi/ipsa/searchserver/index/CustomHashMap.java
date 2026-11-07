package ua.kpi.ipsa.searchserver.index;

import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReferenceArray;
import java.util.concurrent.locks.ReentrantLock;

public class CustomHashMap<K> {

    private static final int DEFAULT_INITIAL_CAPACITY = 1024;
    private static final int MAXIMUM_CAPACITY = 1 << 30;
    private static final int LOCK_COUNT = 256;
    private static final double DEFAULT_LOAD_FACTOR = 0.75;

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

    private volatile AtomicReferenceArray<Entry<K>> buckets;
    private final ReentrantLock[] locks = new ReentrantLock[LOCK_COUNT];
    private final AtomicInteger keyCount = new AtomicInteger(0);
    private final double loadFactor;

    public CustomHashMap() {
        this(DEFAULT_INITIAL_CAPACITY, DEFAULT_LOAD_FACTOR);
    }

    public CustomHashMap(int initialCapacity, double loadFactor) {
        int capacity = LOCK_COUNT;
        while (capacity < initialCapacity && capacity < MAXIMUM_CAPACITY) {
            capacity <<= 1;
        }
        this.buckets = new AtomicReferenceArray<>(capacity);
        this.loadFactor = (loadFactor > 0.0 && loadFactor < 1.0) ? loadFactor : DEFAULT_LOAD_FACTOR;

        for (int i = 0; i < LOCK_COUNT; i++) {
            locks[i] = new ReentrantLock();
        }
    }

    private int bucketIndex(K key, int capacity) {
        int h = key.hashCode();
        h ^= (h >>> 16);
        return h & (capacity - 1);
    }

    private ReentrantLock lockFor(int bucketIdx) {
        return locks[bucketIdx & (LOCK_COUNT - 1)];
    }

    public ConcurrentPostingList getOrCreate(K key) {
        AtomicReferenceArray<Entry<K>> currentBuckets = this.buckets;
        int idx = bucketIndex(key, currentBuckets.length());

        Entry<K> existing = findInBucket(currentBuckets.get(idx), key);
        if (existing != null) {
            return existing.value;
        }

        ReentrantLock lock = lockFor(idx);
        lock.lock();
        ConcurrentPostingList createdList = null;
        try {
            currentBuckets = this.buckets;
            idx = bucketIndex(key, currentBuckets.length());

            existing = findInBucket(currentBuckets.get(idx), key);
            if (existing != null) {
                return existing.value;
            }

            ConcurrentPostingList newList = new ConcurrentPostingList();
            Entry<K> newEntry = new Entry<>(key, newList, currentBuckets.get(idx));
            currentBuckets.set(idx, newEntry);
            keyCount.incrementAndGet();
            createdList = newList;
        } finally {
            lock.unlock();
        }

        if (keyCount.get() >= currentBuckets.length() * loadFactor) {
            resize();
        }

        return createdList;
    }

    public ConcurrentPostingList get(K key) {
        AtomicReferenceArray<Entry<K>> currentBuckets = this.buckets;
        int idx = bucketIndex(key, currentBuckets.length());
        Entry<K> found = findInBucket(currentBuckets.get(idx), key);
        if (found != null) {
            return found.value;
        }
        if (currentBuckets != this.buckets) {
            currentBuckets = this.buckets;
            idx = bucketIndex(key, currentBuckets.length());
            found = findInBucket(currentBuckets.get(idx), key);
            return found != null ? found.value : null;
        }
        return null;
    }

    private void resize() {
        for (int i = 0; i < LOCK_COUNT; i++) {
            locks[i].lock();
        }
        try {
            AtomicReferenceArray<Entry<K>> oldBuckets = this.buckets;
            int oldCapacity = oldBuckets.length();
            if (oldCapacity >= MAXIMUM_CAPACITY) {
                return;
            }
            if (keyCount.get() < oldCapacity * loadFactor) {
                return;
            }

            int newCapacity = oldCapacity << 1;
            AtomicReferenceArray<Entry<K>> newBuckets = new AtomicReferenceArray<>(newCapacity);

            for (int i = 0; i < oldCapacity; i++) {
                Entry<K> current = oldBuckets.get(i);
                while (current != null) {
                    Entry<K> next = current.next;
                    int newIdx = bucketIndex(current.key, newCapacity);
                    Entry<K> newHead = new Entry<>(current.key, current.value, newBuckets.get(newIdx));
                    newBuckets.set(newIdx, newHead);
                    current = next;
                }
            }

            this.buckets = newBuckets;
        } finally {
            for (int i = LOCK_COUNT - 1; i >= 0; i--) {
                locks[i].unlock();
            }
        }
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

    public int capacity() {
        return buckets.length();
    }
}
