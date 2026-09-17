export function parsePair(input: string) {
  const [key, value] = input.split(':');
  return { key, value };
}
