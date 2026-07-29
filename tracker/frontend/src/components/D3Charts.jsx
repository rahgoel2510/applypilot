/**
 * D3-powered chart components for ApplyPilot Dashboard
 * Animated, interactive, visually striking.
 */
import { useRef, useEffect, useMemo } from 'react';
import * as d3 from 'd3';

// ═══════════════════════════════════════════════════════════════
// ANIMATED FUNNEL CHART — Progressive horizontal bars with animation
// ═══════════════════════════════════════════════════════════════

export function FunnelChart({ data, height = 260 }) {
  const svgRef = useRef(null);

  useEffect(() => {
    if (!svgRef.current || !data || data.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth;
    const margin = { top: 10, right: 60, left: 100, bottom: 10 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const maxVal = d3.max(data, d => d.count) || 1;

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const y = d3.scaleBand().domain(data.map(d => d.label)).range([0, innerH]).padding(0.35);
    const x = d3.scaleLinear().domain([0, maxVal]).range([0, innerW]);

    // Background bars (track)
    g.selectAll('.track')
      .data(data)
      .enter().append('rect')
      .attr('class', 'track')
      .attr('x', 0)
      .attr('y', d => y(d.label))
      .attr('width', innerW)
      .attr('height', y.bandwidth())
      .attr('rx', y.bandwidth() / 2)
      .attr('fill', '#EAEDED');

    // Animated value bars
    g.selectAll('.bar')
      .data(data)
      .enter().append('rect')
      .attr('class', 'bar')
      .attr('x', 0)
      .attr('y', d => y(d.label))
      .attr('width', 0)
      .attr('height', y.bandwidth())
      .attr('rx', y.bandwidth() / 2)
      .attr('fill', d => d.color)
      .attr('opacity', 0.9)
      .transition()
      .duration(800)
      .delay((_, i) => i * 120)
      .ease(d3.easeElasticOut.amplitude(1).period(0.5))
      .attr('width', d => Math.max(x(d.count), y.bandwidth()));

    // Glow effect on bars
    g.selectAll('.glow')
      .data(data)
      .enter().append('rect')
      .attr('x', 0)
      .attr('y', d => y(d.label) + 2)
      .attr('width', 0)
      .attr('height', y.bandwidth() - 4)
      .attr('rx', (y.bandwidth() - 4) / 2)
      .attr('fill', d => d.color)
      .attr('opacity', 0.2)
      .attr('filter', 'blur(4px)')
      .transition()
      .duration(800)
      .delay((_, i) => i * 120)
      .attr('width', d => Math.max(x(d.count), y.bandwidth()));

    // Labels (left — stage name)
    g.selectAll('.label')
      .data(data)
      .enter().append('text')
      .attr('x', -10)
      .attr('y', d => y(d.label) + y.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .attr('font-size', '13px')
      .attr('font-weight', '500')
      .attr('fill', '#16191F')
      .text(d => d.label);

    // Value labels (right of bar)
    g.selectAll('.value')
      .data(data)
      .enter().append('text')
      .attr('x', d => Math.max(x(d.count), y.bandwidth()) + 8)
      .attr('y', d => y(d.label) + y.bandwidth() / 2)
      .attr('dy', '0.35em')
      .attr('font-size', '14px')
      .attr('font-weight', '700')
      .attr('fill', d => d.color)
      .attr('opacity', 0)
      .transition()
      .duration(600)
      .delay((_, i) => i * 120 + 400)
      .attr('opacity', 1)
      .textTween(function(d) {
        const i = d3.interpolateNumber(0, d.count);
        return function(t) { return Math.round(i(t)).toString(); };
      });

  }, [data, height]);

  return <svg ref={svgRef} width="100%" height={height} style={{ overflow: 'visible' }} />;
}

// ═══════════════════════════════════════════════════════════════
// SCORE DONUT — Animated donut with center text showing distribution
// ═══════════════════════════════════════════════════════════════

export function ScoreDonut({ data, size = 220 }) {
  const svgRef = useRef(null);

  useEffect(() => {
    if (!svgRef.current || !data || data.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const radius = size / 2;
    const innerRadius = radius * 0.55;
    const total = d3.sum(data, d => d.count);

    const g = svg.append('g').attr('transform', `translate(${radius},${radius})`);

    const pie = d3.pie().value(d => d.count).sort(null).padAngle(0.03);
    const arc = d3.arc().innerRadius(innerRadius).outerRadius(radius - 4);
    const arcHover = d3.arc().innerRadius(innerRadius).outerRadius(radius);

    const arcs = g.selectAll('.arc')
      .data(pie(data.filter(d => d.count > 0)))
      .enter().append('g')
      .attr('class', 'arc');

    // Animated arcs
    arcs.append('path')
      .attr('fill', d => d.data.color)
      .attr('opacity', 0.85)
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .on('mouseenter', function(event, d) {
        d3.select(this)
          .transition().duration(200)
          .attr('d', arcHover)
          .attr('opacity', 1);
        // Show tooltip
        g.select('.tooltip-text').text(`${d.data.range}: ${d.data.count} jobs`);
      })
      .on('mouseleave', function() {
        d3.select(this)
          .transition().duration(200)
          .attr('d', arc)
          .attr('opacity', 0.85);
        g.select('.tooltip-text').text(`${total} total`);
      })
      .transition()
      .duration(1000)
      .delay((_, i) => i * 150)
      .attrTween('d', function(d) {
        const i = d3.interpolate({ startAngle: d.startAngle, endAngle: d.startAngle }, d);
        return function(t) { return arc(i(t)); };
      });

    // Center text
    g.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '-0.2em')
      .attr('font-size', '28px')
      .attr('font-weight', '700')
      .attr('fill', '#16191F')
      .text(total);

    g.append('text')
      .attr('class', 'tooltip-text')
      .attr('text-anchor', 'middle')
      .attr('dy', '1.4em')
      .attr('font-size', '12px')
      .attr('font-weight', '500')
      .attr('fill', '#545B64')
      .text(`${total} total`);

    // Legend below
    const legend = svg.append('g')
      .attr('transform', `translate(${radius - 60}, ${size + 10})`);

    data.filter(d => d.count > 0).forEach((d, i) => {
      const row = legend.append('g').attr('transform', `translate(${(i % 3) * 80}, ${Math.floor(i / 3) * 18})`);
      row.append('circle').attr('r', 5).attr('cx', 5).attr('cy', 0).attr('fill', d.color);
      row.append('text').attr('x', 14).attr('dy', '0.35em').attr('font-size', '11px').attr('fill', '#545B64').text(d.range);
    });

  }, [data, size]);

  const legendHeight = Math.ceil(data.filter(d => d.count > 0).length / 3) * 18 + 15;
  return <svg ref={svgRef} width={size} height={size + legendHeight} style={{ display: 'block', margin: '0 auto' }} />;
}

// ═══════════════════════════════════════════════════════════════
// RADIAL GAUGE — Single value with animated arc (for match rate)
// ═══════════════════════════════════════════════════════════════

export function RadialGauge({ value, max = 100, size = 120, color = '#067D68', label = '' }) {
  const svgRef = useRef(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const radius = size / 2 - 8;
    const g = svg.append('g').attr('transform', `translate(${size / 2},${size / 2})`);

    const startAngle = -Math.PI * 0.75;
    const endAngle = Math.PI * 0.75;
    const angleRange = endAngle - startAngle;
    const valueAngle = startAngle + (value / max) * angleRange;

    const bgArc = d3.arc().innerRadius(radius - 10).outerRadius(radius).startAngle(startAngle).endAngle(endAngle);
    const valArc = d3.arc().innerRadius(radius - 10).outerRadius(radius).startAngle(startAngle);

    // Background track
    g.append('path').attr('d', bgArc()).attr('fill', '#EAEDED');

    // Value arc (animated)
    g.append('path')
      .attr('fill', color)
      .transition()
      .duration(1200)
      .ease(d3.easeElasticOut.amplitude(1).period(0.6))
      .attrTween('d', function() {
        const i = d3.interpolate(startAngle, valueAngle);
        return function(t) { return valArc.endAngle(i(t))(); };
      });

    // Center value
    const valueText = g.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.1em')
      .attr('font-size', '22px')
      .attr('font-weight', '700')
      .attr('fill', color);

    valueText.transition()
      .duration(1000)
      .tween('text', function() {
        const i = d3.interpolateNumber(0, value);
        return function(t) { this.textContent = `${Math.round(i(t))}%`; };
      });

    // Label
    if (label) {
      g.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '2em')
        .attr('font-size', '11px')
        .attr('font-weight', '500')
        .attr('fill', '#545B64')
        .text(label);
    }
  }, [value, max, size, color, label]);

  return <svg ref={svgRef} width={size} height={size} style={{ display: 'block', margin: '0 auto' }} />;
}

// ═══════════════════════════════════════════════════════════════
// SPARKLINE — Tiny animated line chart for stat cards
// ═══════════════════════════════════════════════════════════════

export function Sparkline({ data, width = 100, height = 32, color = '#0073BB' }) {
  const svgRef = useRef(null);

  useEffect(() => {
    if (!svgRef.current || !data || data.length < 2) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const x = d3.scaleLinear().domain([0, data.length - 1]).range([2, width - 2]);
    const y = d3.scaleLinear().domain([0, d3.max(data) || 1]).range([height - 2, 2]);

    const line = d3.line().x((_, i) => x(i)).y(d => y(d)).curve(d3.curveMonotoneX);
    const area = d3.area().x((_, i) => x(i)).y0(height).y1(d => y(d)).curve(d3.curveMonotoneX);

    // Gradient fill
    const grad = svg.append('defs').append('linearGradient')
      .attr('id', `spark-grad-${Math.random().toString(36).slice(2)}`)
      .attr('x1', '0%').attr('y1', '0%').attr('x2', '0%').attr('y2', '100%');
    grad.append('stop').attr('offset', '0%').attr('stop-color', color).attr('stop-opacity', 0.3);
    grad.append('stop').attr('offset', '100%').attr('stop-color', color).attr('stop-opacity', 0);

    // Area
    svg.append('path')
      .attr('d', area(data))
      .attr('fill', `url(#${grad.attr('id')})`)
      .attr('opacity', 0)
      .transition().duration(600).attr('opacity', 1);

    // Line
    const path = svg.append('path')
      .attr('d', line(data))
      .attr('fill', 'none')
      .attr('stroke', color)
      .attr('stroke-width', 2)
      .attr('stroke-linecap', 'round');

    // Animate line drawing
    const totalLength = path.node().getTotalLength();
    path
      .attr('stroke-dasharray', `${totalLength} ${totalLength}`)
      .attr('stroke-dashoffset', totalLength)
      .transition().duration(1000).ease(d3.easeQuadOut)
      .attr('stroke-dashoffset', 0);

    // End dot
    svg.append('circle')
      .attr('cx', x(data.length - 1))
      .attr('cy', y(data[data.length - 1]))
      .attr('r', 3)
      .attr('fill', color)
      .attr('opacity', 0)
      .transition().delay(900).duration(300)
      .attr('opacity', 1);

  }, [data, width, height, color]);

  return <svg ref={svgRef} width={width} height={height} />;
}
