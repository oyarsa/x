function ,fx
    # Handle single argument case
    if test (count $argv) -eq 1
        if not test -f "$argv[1]"
            echo "File not found: $argv[1]"
            return 1
        end

        if string match -q -- '*.gz' "$argv[1]"
            gunzip -c "$argv[1]" | fx
        else if string match -q -- '*.zst' "$argv[1]"
            zstd -dc "$argv[1]" | fx
        else
            fx "$argv[1]"
        end

        # Handle two argument case (query + file)
    else if test (count $argv) -eq 2
        if not test -f "$argv[2]"
            echo "File not found: $argv[2]"
            return 1
        end

        if string match -q -- '*.gz' "$argv[2]"
            gunzip -c "$argv[2]" | fx $argv[1]
        else if string match -q -- '*.zst' "$argv[2]"
            zstd -dc "$argv[2]" | fx $argv[1]
        else
            fx $argv[1] <"$argv[2]"
        end

    else
        echo "Usage: ,fx [query] file"
        return 1
    end
end
