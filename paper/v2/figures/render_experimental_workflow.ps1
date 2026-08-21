param(
    [string]$MermaidCli = "C:\nvm4w\nodejs\npx.cmd"
)

$ErrorActionPreference = "Stop"
$figureDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourcePath = Join-Path $figureDir "experimental_workflow.mmd"
$outputPath = Join-Path $figureDir "experimental_workflow.svg"

& $MermaidCli -y '@mermaid-js/mermaid-cli' `
    -i $sourcePath `
    -o $outputPath `
    -b transparent `
    -w 2400

if ($LASTEXITCODE -ne 0) {
    throw "Mermaid rendering failed with exit code $LASTEXITCODE."
}

# Original monochrome line icons. Coordinates match the four stage headers in
# the landscape Mermaid layout. Re-running this script regenerates the base SVG
# and then applies the icons, keeping the process reproducible.
$icons = @'
<g id="stage-icons" fill="none" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" aria-hidden="true">
  <!-- Stage 2 to Stage 3: routed to terminate above the Evaluation header. -->
  <path d="M978 574 V652" stroke="#59636E" stroke-width="1.6" marker-end="url(#my-svg_flowchart-v2-pointEnd__59636E)"/>
  <!-- Code document: benchmark construction -->
  <g transform="translate(282 124)" stroke="#284D6B">
    <path d="M2 1.5h7l3 3v10H2z"/><path d="M9 1.5v3h3"/>
    <path d="m5.5 8-2 1.5 2 1.5M8.5 8l2 1.5-2 1.5"/>
  </g>
  <!-- Processor: test generation -->
  <g transform="translate(889 38)" stroke="#31573D">
    <rect x="3" y="3" width="10" height="10" rx="1.5"/><rect x="6" y="6" width="4" height="4" rx=".5"/>
    <path d="M6 1v2M10 1v2M6 13v2M10 13v2M1 6h2M1 10h2M13 6h2M13 10h2"/>
  </g>
  <!-- Check circle: automated evaluation -->
  <g transform="translate(911 672)" stroke="#754B17">
    <circle cx="8" cy="8" r="6.5"/><path d="m4.8 8.1 2.1 2.1 4.4-4.5"/>
  </g>
  <!-- Bar chart: statistical analysis -->
  <g transform="translate(270 733)" stroke="#553E69">
    <path d="M2 1.5v13h13"/><rect x="4.5" y="9" width="2.2" height="3"/><rect x="8.2" y="6" width="2.2" height="6"/><rect x="11.9" y="3" width="2.2" height="9"/>
  </g>
</g>
'@

$svg = [System.IO.File]::ReadAllText($outputPath)
$arialOverride = '<style id="publication-font">text,tspan,.label,.nodeLabel,.cluster-label,foreignObject div,foreignObject span,foreignObject p{font-family:Arial,sans-serif!important}</style>'
$svg = $svg -replace '(<svg[^>]*>)', ('$1' + $arialOverride)
$svg = [System.Text.RegularExpressions.Regex]::Replace(
    $svg,
    '<path[^>]*id="my-svg-L_SUITES_CANDIDATES_0"[^>]*/>',
    ''
)
$svg = [System.Text.RegularExpressions.Regex]::Replace(
    $svg,
    '<g class="cluster-label" transform="translate\(([^,]+), 8\)">',
    '<g class="cluster-label" transform="translate($1, 13)">'
)
$svg = [System.Text.RegularExpressions.Regex]::Replace(
    $svg,
    '<g id="stage-icons"[\s\S]*?</g>\s*</g>\s*</svg>$',
    '</g></svg>'
)
$svg = $svg -replace '</svg>$', ($icons + "`n</svg>")
[System.IO.File]::WriteAllText(
    $outputPath,
    $svg,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Rendered $outputPath with four embedded vector stage icons."
