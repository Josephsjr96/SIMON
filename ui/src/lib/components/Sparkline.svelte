<script lang="ts">
  // Tiny inline SVG sparkline. Nulls are gaps; scale is [0, max] so a flat idle line sits at the bottom.
  let { values, max = null, color = '#22c55e' }: { values: (number | null)[]; max?: number | null; color?: string } = $props();
  const W = 200, H = 36;
  const top = $derived(max ?? Math.max(1, ...values.filter((v): v is number => v != null)));
  const d = $derived(
    values
      .map((v, i) => {
        if (v == null) return '';
        const x = values.length > 1 ? (i / (values.length - 1)) * W : W;
        const y = H - 2 - (Math.min(v, top) / top) * (H - 4);
        const prev = i > 0 && values[i - 1] != null;
        return `${prev ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join('')
  );
</script>

<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" class="h-9 w-full" aria-hidden="true">
  <path d={d} fill="none" stroke={color} stroke-width="1.5" vector-effect="non-scaling-stroke" />
</svg>
