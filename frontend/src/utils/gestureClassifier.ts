/**
 * utils/gestureClassifier.ts
 * --------------------------
 * Rule-based sign-language gesture classifier from MediaPipe hand landmarks.
 * Zero network latency — runs entirely in the browser in <1 ms per frame.
 *
 * MediaPipe landmark indices:
 *   0  = WRIST
 *   1–4  = THUMB  (CMC, MCP, IP, TIP)
 *   5–8  = INDEX  (MCP, PIP, DIP, TIP)
 *   9–12 = MIDDLE (MCP, PIP, DIP, TIP)
 *   13–16= RING   (MCP, PIP, DIP, TIP)
 *   17–20= PINKY  (MCP, PIP, DIP, TIP)
 */

export interface ClassifyResult {
    label: string;
    text: string;
    confidence: number;
}

interface LM { x: number; y: number; z: number }

/** Finger extended: tip is above its PIP joint (y decreases upward in normalised coords). */
function extended(tip: LM, pip: LM): boolean {
    return tip.y < pip.y - 0.04;
}

/** Thumb open: tip is far from the base of the index finger (handedness-independent). */
function thumbOpen(thumb_tip: LM, index_mcp: LM): boolean {
    return Math.hypot(thumb_tip.x - index_mcp.x, thumb_tip.y - index_mcp.y) > 0.10;
}

/** Euclidean distance between two landmarks (2-D, ignores z). */
function dist2(a: LM, b: LM): number {
    return Math.hypot(a.x - b.x, a.y - b.y);
}

export function classifyGesture(landmarks: LM[], _handedness?: 'Left' | 'Right'): ClassifyResult {
    if (landmarks.length < 21) return { label: 'unknown', text: '', confidence: 0.0 };

    const wrist = landmarks[0];
    const thumb_tip = landmarks[4];
    const idx_mcp = landmarks[5];
    const idx_pip = landmarks[6];
    const idx_tip = landmarks[8];
    const mid_pip = landmarks[10];
    const mid_tip = landmarks[12];
    const ring_pip = landmarks[14];
    const ring_tip = landmarks[16];
    const pink_pip = landmarks[18];
    const pink_tip = landmarks[20];

    const th = thumbOpen(thumb_tip, idx_mcp);
    const idx = extended(idx_tip, idx_pip);
    const mid = extended(mid_tip, mid_pip);
    const ring = extended(ring_tip, ring_pip);
    const pink = extended(pink_tip, pink_pip);

    // OK sign: thumb and index tips pinched, remaining three fingers open
    if (dist2(thumb_tip, idx_tip) < 0.07 && mid && ring && pink)
        return { label: 'ok_sign', text: 'OK', confidence: 0.90 };

    // I Love You: thumb + index + pinky extended
    if (th && idx && !mid && !ring && pink)
        return { label: 'i_love_you', text: 'I love you', confidence: 0.90 };

    // Shaka / Hang Loose: thumb + pinky only
    if (th && !idx && !mid && !ring && pink)
        return { label: 'shaka', text: 'Hang loose', confidence: 0.85 };

    // Rock On: index + pinky extended, no thumb
    if (!th && idx && !mid && !ring && pink)
        return { label: 'rock_on', text: 'Rock on', confidence: 0.85 };

    // Peace / Victory: index + middle
    if (!th && idx && mid && !ring && !pink)
        return { label: 'peace', text: 'Peace', confidence: 0.90 };

    // Pointing: only index
    if (!th && idx && !mid && !ring && !pink)
        return { label: 'pointing', text: 'One', confidence: 0.85 };

    // Thumbs up: thumb open, fist closed, tip above wrist
    if (th && !idx && !mid && !ring && !pink && thumb_tip.y < wrist.y - 0.03)
        return { label: 'thumbs_up', text: 'Good', confidence: 0.90 };

    // Thumbs down: thumb open, fist closed, tip below wrist
    if (th && !idx && !mid && !ring && !pink && thumb_tip.y > wrist.y + 0.03)
        return { label: 'thumbs_down', text: 'No', confidence: 0.80 };

    // Open hand (all four fingers extended)
    if (idx && mid && ring && pink)
        return { label: 'open_hand', text: 'Hello', confidence: 0.85 };

    // Fist (all closed)
    if (!th && !idx && !mid && !ring && !pink)
        return { label: 'fist', text: 'Yes', confidence: 0.80 };

    return { label: 'unknown', text: '', confidence: 0.0 };
}
