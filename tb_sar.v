`timescale 1ns/1ps
// Self-checking testbench for sar_logic.
//  * Behavioural capacitor DAC (real-valued weights) + comparator around the device under test.
//  * Reads weights.txt (N lines, bit 0 first, in LSB) and inputs.txt (one input per line, in LSB).
//  * For every input it runs one conversion and checks the result against a golden binary-search
//    model written inside this testbench (independent of the RTL).
//  * Also checks: one done pulse per conversion, and sample low for exactly N cycles per conversion.
//  * Writes every output code to codes_verilog.txt (used by verilog_check.py for the Python cross-check).
//  * Prints a clock-by-clock trace of conversion number TRACE_AT.
module tb_sar;
    parameter N = 10;
    parameter TRACE_AT = 309;               // conversion number to trace (0 = no trace)

    reg clk = 0, rst_n = 0, start = 0;
    reg comp_r = 0;
    wire comp_in = comp_r;
    wire [N-1:0] sar_out;
    wire valid, done, sample;
    real w [0:N-1];
    real vin, tmp;
    integer fw, fi, fo, r, i, cycles, first;
    integer conv_count = 0, done_count = 0, mismatches = 0, low_cnt = 0, sample_errors = 0;
    reg trace = 0;
    reg [N-1:0] golden_code;

    sar_logic #(.N(N)) dut (.clk(clk), .rst_n(rst_n), .start(start), .comp_in(comp_in),
                            .sar_out(sar_out), .valid(valid), .done(done), .sample(sample));
    always #5 clk = ~clk;

    // Capacitor DAC: sum of the weights of the set bits, MSB first (same order as the Python model)
    function real dac;
        input [N-1:0] code;
        integer k;
        real s;
        begin
            s = 0.0;
            for (k = N - 1; k >= 0; k = k - 1)
                if (code[k]) s = s + w[k];
            dac = s;
        end
    endfunction

    // Golden model: plain binary search with the real weights
    function [N-1:0] golden;
        input real v;
        integer k;
        real acc, trial;
        reg [N-1:0] c;
        begin
            acc = 0.0; c = {N{1'b0}};
            for (k = N - 1; k >= 0; k = k - 1) begin
                trial = acc + w[k];
                if (v >= trial) begin acc = trial; c[k] = 1'b1; end
            end
            golden = c;
        end
    endfunction

    always @(sar_out) comp_r = (vin >= dac(sar_out));      // comparator: 1 if Vin >= Vdac
    always @(posedge clk) if (done) done_count = done_count + 1;
    always @(negedge clk) if (!sample) low_cnt = low_cnt + 1;
    always @(posedge clk) if (trace)
        $display("TRACE t=%0d ns  start=%b  mask=%b  sar_out=%b  comp_in=%b  valid=%b  done=%b",
                 $time, start, dut.mask, sar_out, comp_in, valid, done);

    initial begin
        fw = $fopen("weights.txt", "r");
        for (i = 0; i < N; i = i + 1) begin r = $fscanf(fw, "%f\n", tmp); w[i] = tmp; end
        $fclose(fw);
        fi = $fopen("inputs.txt", "r");
        fo = $fopen("codes_verilog.txt", "w");
        vin = 0.0;
        #23 rst_n = 1;                                      // release reset
        first = 1;
        while (!$feof(fi)) begin
            r = $fscanf(fi, "%f\n", tmp);
            if (r == 1) begin
                @(negedge clk);
                vin = tmp;
                comp_r = (vin >= dac(sar_out));
                conv_count = conv_count + 1;
                if (conv_count == TRACE_AT) trace = 1;
                low_cnt = 0;
                start = 1;                                  // one-cycle start pulse
                cycles = 0;
                @(negedge clk);
                start = 0;
                while (valid !== 1'b1) begin @(negedge clk); cycles = cycles + 1; end
                if (first) begin
                    $display("clock edges from start to valid = %0d (1 start edge + %0d decisions)", cycles + 1, cycles);
                    first = 0;
                end
                @(negedge clk);
                trace = 0;
                golden_code = golden(vin);
                if (sar_out !== golden_code) begin
                    mismatches = mismatches + 1;
                    if (mismatches <= 5) $display("MISMATCH vin=%f dut=%0d golden=%0d", vin, sar_out, golden_code);
                end
                if (low_cnt !== N) sample_errors = sample_errors + 1;
                $fdisplay(fo, "%0d", sar_out);
            end
        end
        $fclose(fi); $fclose(fo);
        $display("conversions = %0d, mismatches vs golden = %0d, done pulses = %0d, sample errors = %0d",
                 conv_count, mismatches, done_count, sample_errors);
        if (mismatches == 0 && done_count == conv_count && sample_errors == 0)
            $display("PASS");
        else
            $display("FAIL");
        $finish;
    end
endmodule
