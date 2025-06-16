import numpy as np
from cykhash import Int64toInt64Map

class NodeStore:
    def __init__(self, initial_capacity=1024):
        self.size = 0
        self.capacity = initial_capacity
        self.index_map = Int64toInt64Map()
        self.data = np.empty((self.capacity, 2), dtype=np.float64)

    def _resize(self):
        # Double the capacity
        self.capacity *= 2
        new_data = np.empty((self.capacity, 2), dtype=np.float64)
        new_data[:self.size] = self.data  # Copy old data
        self.data = new_data

    def append(self, key, value_tuple):
        """
        Insert a new key-value pair into the store.

        Args:
            key (int): The key to insert.
            value_tuple (tuple of floats): The associated value tuple.
        """
        if key in self.index_map:
            return self.set(key, value_tuple)

        self.index_map[key] = self.size
        if self.size >= self.capacity:
            self._resize()
        self.data[self.size] = value_tuple
        self.size += 1

    def set(self, key, value_tuple):
        """
        Set the value of the key in the store.

        Args:
            key (int): The key to modify.
            value_tuple (tuple of floats): The new value tuple.
        """
        if not key in self.index_map:
            raise KeyError(f"Key does not exist.")
        idx = self.index_map.get(key)
        self.data[idx] = value_tuple

    def compact(self):
        """
        Compact the internal storage NumPy array for memory efficiency.
        """
        self.data = self.data[:self.size]
        self.capacity = self.size

    def get(self, key):
        """Retrieve the value tuple for a given key."""
        idx = self.index_map.get(key)
        if idx is not None:
            return self.data[idx]
        return None

    def __contains__(self, key):
        """Check if a key exists in the store."""
        return key in self.index_map

    def __len__(self):
        """Return the number of stored keys."""
        return len(self.index_map)
