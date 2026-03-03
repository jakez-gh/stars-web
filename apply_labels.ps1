$repo = "jakez-gh/stars-web"

$assignments = @(
    @{ n=9;  l="tier-2-orders,layer:ui,layer:api,layer:state" },
    @{ n=10; l="tier-2-orders,layer:ui,layer:api,layer:state" },
    @{ n=11; l="tier-3-turns,layer:binary" },
    @{ n=12; l="tier-3-turns,layer:ui,layer:api" },
    @{ n=33; l="tier-2-orders,layer:ui" },
    @{ n=34; l="tier-2-orders,layer:ui,blocked" },
    @{ n=35; l="tier-2-orders,layer:api,layer:state,blocked" },
    @{ n=36; l="tier-2-orders,layer:ui,layer:api,blocked" },
    @{ n=37; l="tier-2-orders,layer:test,blocked" },
    @{ n=39; l="tier-2-orders,layer:ui" },
    @{ n=40; l="tier-2-orders,layer:ui,blocked" },
    @{ n=41; l="tier-2-orders,layer:ui,blocked" },
    @{ n=42; l="tier-2-orders,layer:api,layer:state,blocked" },
    @{ n=43; l="tier-2-orders,layer:ui,layer:api,blocked" },
    @{ n=44; l="tier-2-orders,layer:test,blocked" },
    @{ n=45; l="tier-3-turns,layer:docs,layer:binary" },
    @{ n=46; l="tier-3-turns,layer:binary,blocked" },
    @{ n=47; l="tier-3-turns,layer:binary,blocked" },
    @{ n=48; l="tier-3-turns,layer:test,layer:binary,blocked" },
    @{ n=49; l="tier-3-turns,layer:ui,blocked" },
    @{ n=50; l="tier-3-turns,layer:api,blocked" },
    @{ n=51; l="tier-3-turns,layer:ui,blocked" },
    @{ n=52; l="tier-3-turns,layer:state,layer:ui,blocked" },
    @{ n=53; l="tier-3-turns,layer:ui,blocked" }
)

$ok = 0; $fail = 0
foreach ($a in $assignments) {
    $out = gh issue edit $a.n --repo $repo --add-label $a.l 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK  #$($a.n)  [$($a.l)]"
        $ok++
    } else {
        Write-Host "FAIL #$($a.n): $out"
        $fail++
    }
}

Write-Host ""
Write-Host "Results: $ok succeeded, $fail failed"
Write-Host "Done."
