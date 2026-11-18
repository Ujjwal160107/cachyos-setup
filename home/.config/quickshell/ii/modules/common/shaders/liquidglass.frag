#version 440
// Liquid glass for surfaces the compositor's glass plugin can't reach (the
// lock screen). The same optics as hyprglass, in the shell: the glass takes
// its shape from `mask` (any item's alpha), reads its height from `field`
// (that shape blurred by about the bezel width), and refracts `behind`.
//
// Compile: qsb --glsl "100 es,120,150" -o liquidglass.frag.qsb liquidglass.frag

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 itemSize;     // px of the padded box all three textures cover
    float bezel;       // px of curved rim
    float refraction;  // px the rim shifts what is behind it
    float bodyLens;    // magnification across the whole pane (0.03 = 3%)
    float frost;       // px of blur in what shows through
    float rim;         // brightness of the one-pixel edge
    float brightness;
    float adaptiveDim; // dark mode: how hard bright backdrops are pulled down (readability)
    vec4 tint;         // rgb, a = amount
    float dispersion;  // chromatic split at the rim
    float shadow;      // soft drop shadow under the glass
    float adaptiveBoost; // light mode: how hard dark backdrops are lifted (readability)
    float highlightDirection; // where the rim catches light: 0 all round, 1 the top, 2 the top left
    float darkEdge;      // alpha of the thin dark line inside the rim (0.88 dark mode, 0.43 light)
    float nearReflection; // how much the rim takes its colour from just outside the glass
};
layout(binding = 1) uniform sampler2D mask;
layout(binding = 2) uniform sampler2D field;
layout(binding = 3) uniform sampler2D behind;

const float CEILING = 0.30;
const float FLOOR = 0.74;

float luma(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

vec3 backdrop(vec2 uv, vec2 px) {
    if (frost < 0.01)
        return texture(behind, uv).rgb;
    vec2 d = frost * px;
    return (texture(behind, uv).rgb * 2.0
          + texture(behind, uv + vec2(d.x, d.y)).rgb + texture(behind, uv + vec2(-d.x, d.y)).rgb
          + texture(behind, uv + vec2(d.x, -d.y)).rgb + texture(behind, uv + vec2(-d.x, -d.y)).rgb) / 6.0;
}

void main() {
    vec2 uv = qt_TexCoord0;
    vec2 px = 1.0 / itemSize;

    float coverage = texture(mask, uv).a;

    // Outside the shape: only a soft shadow, which keeps the glass apart from what is behind
    if (coverage < 0.002) {
        float s = texture(field, uv - vec2(0.0, 3.0) * px).a;
        fragColor = vec4(0.0, 0.0, 0.0, shadow * pow(clamp(s * 2.0, 0.0, 1.0), 1.6)) * qt_Opacity;
        return;
    }

    // The crisp rim: where coverage falls off within one pixel
    float n4 = min(min(texture(mask, uv + vec2(px.x, 0.0)).a, texture(mask, uv - vec2(px.x, 0.0)).a),
                   min(texture(mask, uv + vec2(0.0, px.y)).a, texture(mask, uv - vec2(0.0, px.y)).a));
    float line = clamp(coverage - n4, 0.0, 1.0);

    // The bezel: the blurred shape is the glass's height. Its gradient points
    // inward and is steepest at the edge, flat deep inside.
    vec2 g = vec2(texture(field, uv + vec2(px.x, 0.0)).a - texture(field, uv - vec2(px.x, 0.0)).a,
                  texture(field, uv + vec2(0.0, px.y)).a - texture(field, uv - vec2(0.0, px.y)).a) * 0.5;
    float slope = clamp(length(g) * bezel * 2.5, 0.0, 1.0);
    vec2 inward = length(g) > 1e-6 ? normalize(g) : vec2(0.0);

    // Refraction: the rim shows what lies just outside it, squeezed in; the
    // whole pane is a shallow magnifier
    vec3 raw = backdrop(uv, px); // what is behind, before any toning

    vec2 offset = -inward * pow(slope, 1.5) * refraction * px - (uv - 0.5) * bodyLens;
    vec3 color = vec3(backdrop(uv + offset * (1.0 + dispersion), px).r,
                      backdrop(uv + offset, px).g,
                      backdrop(uv + offset * (1.0 - dispersion), px).b);

    // Tone. Dark mode: smoked, with bright backdrops pulled down so white text
    // on the glass stays readable. Light mode, the mirror: milky, with dark
    // backdrops lifted toward a floor (white mixed in) so dark text stays readable.
    float l = luma(color);
    float toned = l - max(l - CEILING, 0.0) * adaptiveDim;
    color *= brightness * (l > 1e-4 ? toned / l : 1.0);
    if (adaptiveBoost > 0.001) {
        float m = luma(color);
        float lifted = m + max(FLOOR - m, 0.0) * adaptiveBoost;
        color = mix(color, vec3(1.0), clamp((lifted - m) / max(1.0 - m, 1e-3), 0.0, 1.0));
    }
    color = mix(color, tint.rgb, tint.a);

    // Light, as in hyprglass. The rim is lit most along the top (or from the
    // top left), takes the colour of what is behind and near it, brightening
    // over bright content and nearly vanishing over black (Tahoe's rim:
    // 1.45 luma + 3 chroma + 0.05), with a thin dark line inside it that
    // shows on the sides (iOS 27).
    vec2 nOut = -inward;
    float lobe = 1.0, sideOn = 1.0;
    if (highlightDirection > 1.5) {
        const vec2 L = vec2(-0.70710678, -0.70710678);
        sideOn = abs(dot(nOut, vec2(-L.y, L.x)));
        lobe = max(1.0 - sideOn, 0.15) * (dot(nOut, L) < 0.0 ? 0.6 : 1.0);
    } else if (highlightDirection > 0.5) {
        sideOn = abs(nOut.x);
        lobe = max(1.0 - sideOn, 0.15) * (nOut.y > 0.0 ? 0.6 : 1.0);
    }
    if (darkEdge > 0.001) {
        float dir = highlightDirection < 0.5 ? 1.0 : mix(1.0, sideOn, 0.77);
        color *= 1.0 - darkEdge * line * dir;
    }
    vec3 envC = texture(behind, uv - inward * 5.0 * px).rgb;
    float env = smoothstep(0.30, 0.95, luma(envC));
    color += vec3(slope * slope * 0.06 * (0.3 + 0.7 * env) * lobe);
    vec3 src = mix(raw, envC, nearReflection);
    float srcL = luma(src);
    vec3 rimC = max(vec3(1.45 * srcL + 0.05) + 3.0 * (src - vec3(srcL)), 0.0);
    color = mix(color, rimC, clamp(line * rim * lobe, 0.0, 1.0));

    fragColor = vec4(color * coverage, coverage) * qt_Opacity;
}
