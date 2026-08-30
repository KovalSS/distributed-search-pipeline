package ua.kpi.ipsa.searchserver.threadpool;

import java.util.ArrayDeque;
import java.util.Queue;

public class ThreadSafeTaskQueue<T> {

    private final Queue<T> tasks = new ArrayDeque<>();

    public synchronized void enqueue(T task) {
        tasks.add(task);
    }

    public synchronized T poll() {
        return tasks.poll();
    }

    public synchronized boolean isEmpty() {
        return tasks.isEmpty();
    }

    public synchronized int size() {
        return tasks.size();
    }
}