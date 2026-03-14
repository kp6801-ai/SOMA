CAMELOT_WHEEL = {
    # Sharp notation
    "C major": "8B", "A minor": "8A",
    "G major": "9B", "E minor": "9A",
    "D major": "10B", "B minor": "10A",
    "A major": "11B", "F# minor": "11A",
    "E major": "12B", "C# minor": "12A",
    "B major": "1B", "G# minor": "1A",
    "F# major": "2B", "D# minor": "2A",
    "C# major": "3B", "A# minor": "3A",
    "G# major": "4B", "F minor": "4A",
    "D# major": "5B", "C minor": "5A",
    "A# major": "6B", "G minor": "6A",
    "F major": "7B", "D minor": "7A",
    # Flat equivalents (Essentia returns these)
    "Eb major": "5B", "Eb minor": "2A",
    "Ab major": "4B", "Ab minor": "1A",
    "Bb major": "6B", "Bb minor": "3A",
    "Db major": "3B", "Db minor": "12A",
    "Gb major": "2B", "Gb minor": "11A",
    "Cb major": "1B", "Cb minor": "10A",
}

def get_camelot(key: str) -> str:
    return CAMELOT_WHEEL.get(key, "Unknown")

def compatible_keys(camelot: str) -> list:
    if camelot == "Unknown" or len(camelot) < 2:
        return []
    
    number = int(camelot[:-1])
    letter = camelot[-1]
    
    compatible = []
    
    # Same key
    compatible.append(camelot)
    
    # Adjacent numbers (one step up and down)
    compatible.append(f"{(number % 12) + 1}{letter}")
    compatible.append(f"{((number - 2) % 12) + 1}{letter}")
    
    # Relative major/minor (same number, opposite letter)
    opposite = "A" if letter == "B" else "B"
    compatible.append(f"{number}{opposite}")
    
    return compatible