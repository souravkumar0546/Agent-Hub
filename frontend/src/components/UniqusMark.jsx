/** Uniqus "U" mark — the actual U from the uniqus.com logomark, cropped
 *  out of the wordmark PNG and bundled at /uniqus-mark.png (256x256
 *  transparent PNG). Use everywhere the platform identifies itself
 *  visually at small sizes (chatbot avatar, FAB, etc.). For the full
 *  wordmark, render `/uniqus-logo.png` instead.
 */
export default function UniqusMark({ size = 28, title = 'Uniqus' }) {
  return (
    <img
      src="/uniqus-mark.png"
      width={size}
      height={size}
      alt={title}
      draggable={false}
      style={{ display: 'block', userSelect: 'none' }}
    />
  );
}
