function ,jq
    if not test -f "$argv[2]"
        echo "File not found: $argv[2]"
        return 1
    end

    if string match -q -- '*.gz' "$argv[2]"
        gunzip -c "$argv[2]" | jq $argv[1]
    else if string match -q -- '*.zst' "$argv[2]"
        zstd -dc "$argv[2]" | jq $argv[1]
    else
        jq $argv[1] <"$argv[2]"
    end
end
