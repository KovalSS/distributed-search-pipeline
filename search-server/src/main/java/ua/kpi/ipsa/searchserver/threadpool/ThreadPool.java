package ua.kpi.ipsa.searchserver.threadpool;

import java.util.ArrayList;
import java.util.List;

public class ThreadPool {

    private final ThreadSafeTaskQueue<Runnable> tasks = new ThreadSafeTaskQueue<>();
    private final List<Thread> workers = new ArrayList<>();

    private final Object taskMonitor = new Object();
    private final Object completionMonitor = new Object();

    private int activeTasks = 0;
    private volatile boolean terminated = false;

    public ThreadPool(int workerCount) {
        for (int i = 0; i < workerCount; i++) {
            Thread worker = new Thread(this::routine, "pool-worker-" + i);
            workers.add(worker);
            worker.start();
        }
    }

    public void submit(Runnable task) {
        synchronized (taskMonitor) {
            if (terminated) {
                return;
            }
            synchronized (completionMonitor) {
                activeTasks++;
            }
            tasks.enqueue(task);
            taskMonitor.notify();
        }
    }

    private void routine() {
        while (true) {
            Runnable task;

            synchronized (taskMonitor) {
                while (tasks.isEmpty() && !terminated) {
                    try {
                        taskMonitor.wait();
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        return;
                    }
                }
                if (terminated && tasks.isEmpty()) {
                    return;
                }
                task = tasks.poll();
            }

            if (task != null) {
                try {
                    task.run();
                } finally {
                    synchronized (completionMonitor) {
                        activeTasks--;
                        if (activeTasks == 0) {
                            completionMonitor.notifyAll();
                        }
                    }
                }
            }
        }
    }

    public void awaitCompletion() {
        synchronized (completionMonitor) {
            while (activeTasks > 0) {
                try {
                    completionMonitor.wait();
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return;
                }
            }
        }
    }

    public void shutdown() {
        synchronized (taskMonitor) {
            terminated = true;
            taskMonitor.notifyAll();
        }
        for (Thread worker : workers) {
            try {
                worker.join();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }
}