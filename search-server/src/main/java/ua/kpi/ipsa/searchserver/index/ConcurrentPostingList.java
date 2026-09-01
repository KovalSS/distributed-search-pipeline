package ua.kpi.ipsa.searchserver.index;

import java.util.Iterator;
import java.util.concurrent.atomic.AtomicReference;

public class ConcurrentPostingList implements Iterable<InvertedIndex.Posting> {

    private static class Node {
        final InvertedIndex.Posting value;
        final Node next;

        Node(InvertedIndex.Posting value, Node next) {
            this.value = value;
            this.next = next;
        }
    }

    private final AtomicReference<Node> head = new AtomicReference<>();

    public void add(InvertedIndex.Posting posting) {
        Node newNode;
        Node currentHead;
        do {
            currentHead = head.get();
            newNode = new Node(posting, currentHead);
        } while (!head.compareAndSet(currentHead, newNode));
    }

    @Override
    public Iterator<InvertedIndex.Posting> iterator() {
        return new Iterator<>() {
            private Node current = head.get();

            @Override
            public boolean hasNext() {
                return current != null;
            }

            @Override
            public InvertedIndex.Posting next() {
                InvertedIndex.Posting value = current.value;
                current = current.next;
                return value;
            }
        };
    }
}