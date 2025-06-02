#!/usr/bin/env python3
# Author: Morrow Shore
# License: AGPLv3
# Contact: inquiry@morrowshore.com

import sqlite3
import sys
import os
from datetime import datetime

def get_last_pos(str, source):
    str_find = bytearray(str,'ascii')
    last_pos = 0
    pos = 0
    while True:
        pos = source.find(str_find, last_pos)
        if pos == -1:
            break
        last_pos = pos + 1
    return (last_pos -1)

def extract_png_from_layer(working_file):
    try:
        with open(working_file, "rb") as inputFile:
            content = inputFile.read()
            if content:
                begin_pos = get_last_pos('PNG', content) - 1
                end_pos = get_last_pos('IEND', content) + 4
                
                if begin_pos > 0 and end_pos > begin_pos:
                    with open(working_file+".png", 'wb') as outputFile:
                        outputFile.write(content[begin_pos:end_pos])
                    return True
    except Exception:
        pass
    return False

def extract_sqlite_layers(sut_file):
    try:
        base_name = os.path.splitext(sut_file)[0]
        con = sqlite3.connect(sut_file)
        cur = con.cursor()
        cur.execute("select _PW_ID, FileData from MaterialFile")
        row = cur.fetchone()
        
        extracted_count = 0
        while row:
            layer_file = f"{base_name}_{row[0]}"
            with open(layer_file, 'wb') as f:
                f.write(row[1])
            if extract_png_from_layer(layer_file):
                extracted_count += 1
            os.remove(layer_file)
            row = cur.fetchone()
            
        print(f"Extracted {extracted_count} Brush Tips from {sut_file}")
        cur.close()
    except Exception as e:
        print(f"Error extracting sql layers for brush tip: {e}")

def export_sql_dump(db_path, output_file):
    try:
        conn = sqlite3.connect(db_path)
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")
        print(f"Exported SQL dump to: {output_file}")
    except Exception as e:
        print(f"Error exporting SQL: {e}")
    finally:
        if conn:
            conn.close()

import io
import struct

def format_value_raw(value, name=None):
    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        if len(value) > 300:
            return f"BINARY DATA: {len(value)} bytes"
        return value.hex()
    return str(value)

def format_pressure_graph(data):
    try:
        # header -- 7 uint32 values
        version, count, stride, zero1, zero2, zero3, zero4 = struct.unpack(">7I", data[:28])
        
        # values -- big-endian doubles
        pressures = [
            struct.unpack(">d", data[28+i*8:28+(i+1)*8])[0]
            for i in range(len(data[28:]) // 8)
        ]
        
        output = [
            "",
            "  Header:",
            f"    version = {version}",
            f"    count   = {count}",
            f"    stride  = {stride}",
            f"    zero1   = {zero1}, zero2 = {zero2}, zero3 = {zero3}, zero4 = {zero4}",
            "",
            "  Values:"
        ]
        
        for idx, val in enumerate(pressures, 1):
            output.append(f"    [{idx:2d}] {val:.6f}")
            
        return "\n".join(output)
    except Exception:
        return data.hex()

def format_value(value, name=None, raw_mode=False):
    """Format values—showing structured data for TextureImage bytes."""
    if raw_mode:
        return format_value_raw(value, name)
    if name == "FileData" and isinstance(value, bytes):
        return f"BINARY DATA: {len(value)} bytes (exported as .png)"
    if name == "PressureGraph" and isinstance(value, bytes):
        return format_pressure_graph(value)
    if value is None:
        return "NULL"
            # WITCH CRAFT 
    if isinstance(value, bytes):
        try:
            b = value

            # read the first four 32-bit unsigned integers as big-endian
            a, b_, c, d = struct.unpack(">IIII", b[:16])
            parts = [f"{a}, {b_}, {c}, {d}"]

            # read a null-terminated UTF-16LE string starting at offset `start`
            def _read_utf16le_null(data, start):
                chars = []
                offset = start
                while True:
                    two = data[offset : offset + 2]
                    if len(two) < 2:
                        break
                    code = struct.unpack("<H", two)[0]
                    offset += 2
                    if code == 0:
                        break
                    chars.append(chr(code))
                return "".join(chars), offset

            # read the first UTF-16LE string at offset 16
            s1, off1 = _read_utf16le_null(b, 16)
            parts.append(f"{s1}")

            # after s1’s terminating 0x0000, parse two 16-bit big-endian ints
            #    • int1 is at bytes [off1 .. off1+2)
            #    • skip the next 2 bytes of padding,
            #    • int2 is at bytes [off1+4 .. off1+6)
            int1 = struct.unpack(">H", b[off1 : off1 + 2])[0]
            int2 = struct.unpack(">H", b[off1 + 4 : off1 + 6])[0]
            parts.append(f"{int1}, {int2}")

            # second UTF-16LE string (s2) begins immediately at offset (off1 + 6):
            s2, off2 = _read_utf16le_null(b, off1 + 6)
            parts.append(f"{s2}")

            # after s2’s terminating 0x0000, parse two more 16-bit big-endian ints
            #    • int3 is at bytes [off2 .. off2+2)
            #    • skip the next 2 bytes of padding,
            #    • int4 is at bytes [off2+4 .. off2+6)
            int3 = struct.unpack(">H", b[off2 : off2 + 2])[0]
            int4 = struct.unpack(">H", b[off2 + 4 : off2 + 6])[0]
            parts.append(f"{int3}, {int4}")

            # third UTF-16LE string (s3) begins at offset (off2 + 6)
            s3, _ = _read_utf16le_null(b, off2 + 6)
            parts.append(f"{s3}")

            # assemble shit
            return "\n" + "\n".join(parts)

        except Exception:
            return value.hex()

    return str(value)


def dump_database_to_file(db_path, output_file, raw_mode=False):
    """Dump entire SQLite database into readable text"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA database_list;")
        db_info = cursor.fetchall()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Database Dump of: {os.path.basename(db_path)}\n")
            f.write(f"Generated on: {datetime.now()}\n")
            
            f.write("="*50 + "\n\n")
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            tables = [table[0] for table in cursor.fetchall()]
            
            for table in tables:
                f.write(f"TABLE: {table}\n")
                f.write("="*50 + "\n\n")
                
                cursor.execute(f"PRAGMA table_info({table});")
                columns = cursor.fetchall()
                
                f.write("COLUMN STRUCTURE:\n")
                f.write(f"{'Name':<36} {'Type':<31} {'Nullable':<24} {'Primary Key'}\n")
                f.write("-"*70 + "\n")
                for col in columns:
                    f.write(f"{col[1]:<36} {col[2]:<31} {'YES' if not col[3] else 'NO':<24} {'YES' if col[5] else ''}\n")
                f.write("\n")
                
                cursor.execute(f"SELECT * FROM {table};")
                rows = cursor.fetchall()
                
                if rows:
                    cursor.execute(f"SELECT * FROM {table} LIMIT 0;")
                    col_names = [desc[0] for desc in cursor.description]
                    
                    f.write("DATA CONTENTS:\n")
                    for row_idx, row in enumerate(rows, 1):
                        f.write(f"\nRECORD {row_idx}\n")
                        for name, value in zip(col_names, row):
                            f.write(f"{name:<32}: {format_value(value, name, raw_mode)}\n")
                        f.write("-"*50 + "\n")
                else:
                    f.write("(No data rows in this table)\n")
                
                f.write("\n\n")
        
        print(f"Successfully created dump: {output_file}")
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def main():
    if len(sys.argv) < 2:
        print("Usage: python cspbrushextract.py <input.sut> [--raw]")
        return
    
    input_file = sys.argv[1]
    raw_mode = "--raw" in sys.argv
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        return
    
    base_name = os.path.splitext(input_file)[0]
    output_file = base_name + "_dump.txt"
    sql_file = base_name + "_dump.sql"
    
    dump_database_to_file(input_file, output_file, raw_mode)
    export_sql_dump(input_file, sql_file)
    extract_sqlite_layers(input_file)
    
if __name__ == "__main__":
    main()