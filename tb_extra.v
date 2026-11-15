`timescale 1ns/1ps
module tb_extra;
    parameter N = 10;
    reg clk = 0, rst_n = 0, start = 0;
    reg comp_r = 0;
    wire [N-1:0] sar_out; wire valid, done, sample;
    integer done_cycles = 0;
    always @(posedge clk) if (done) done_cycles = done_cycles + 1;
    real vin;
    sar_logic #(.N(N)) dut (.clk(clk), .rst_n(rst_n), .start(start), .comp_in(comp_r), .sar_out(sar_out), .valid(valid), .done(done), .sample(sample));
    always #5 clk = ~clk;
    always @(sar_out) comp_r = (vin >= sar_out);        // ideal DAC: weights 2^i
    task convert; input real v; begin
        @(negedge clk); vin = v; comp_r = (vin >= sar_out); start = 1;
        @(negedge clk); start = 0;
        while (valid !== 1'b1) @(negedge clk);
        @(negedge clk);
    end endtask
    integer errors = 0;
    initial begin
        vin = 0; #23 rst_n = 1;
        if (sample !== 1'b1) begin errors = errors + 1; $display("FAIL sample high when idle"); end
        // 1) normal conversion
        @(negedge clk); vin = 300.4; comp_r = (vin >= sar_out); start = 1;
        @(negedge clk); start = 0;
        if (sample !== 1'b0) begin errors = errors + 1; $display("FAIL sample low during conversion"); end
        while (valid !== 1'b1) @(negedge clk);
        @(negedge clk);
        if (sample !== 1'b1) begin errors = errors + 1; $display("FAIL sample high after conversion"); end
        if (done_cycles !== 1) begin errors = errors + 1; $display("FAIL done pulse count %0d", done_cycles); end
        if (sar_out !== 300) begin errors = errors + 1; $display("FAIL normal: %0d", sar_out); end
        // 2) valid stays high until the next start
        repeat (5) @(negedge clk);
        if (valid !== 1'b1 || sar_out !== 300) begin errors = errors + 1; $display("FAIL hold"); end
        // 3) reset in the middle of a conversion
        @(negedge clk); vin = 700.2; comp_r = (vin >= sar_out); start = 1;
        @(negedge clk); start = 0;
        repeat (4) @(negedge clk);
        #1 rst_n = 0; #1;
        if (sar_out !== 0 || valid !== 0 || dut.mask !== 0) begin errors = errors + 1; $display("FAIL reset: out=%0d valid=%b mask=%b", sar_out, valid, dut.mask); end
        #10 rst_n = 1;
        // 4) works again after reset
        convert(701.9);
        if (sar_out !== 701) begin errors = errors + 1; $display("FAIL after reset: %0d", sar_out); end
        // 5) start pulse in the middle of a conversion restarts it cleanly
        @(negedge clk); vin = 99.5; comp_r = (vin >= sar_out); start = 1;
        @(negedge clk); start = 0;
        repeat (3) @(negedge clk);
        vin = 12.5; comp_r = (vin >= sar_out); start = 1;
        @(negedge clk); start = 0;
        while (valid !== 1'b1) @(negedge clk);
        @(negedge clk);
        if (sar_out !== 12) begin errors = errors + 1; $display("FAIL restart: %0d", sar_out); end
        // 6) start held high for several cycles keeps the machine at the first trial
        @(negedge clk); vin = 200.5; comp_r = (vin >= sar_out); start = 1;
        repeat (5) @(negedge clk);
        if (valid !== 0 || sar_out !== (1 << (N-1))) begin errors = errors + 1; $display("INFO start held: out=%0d valid=%b", sar_out, valid); end
        start = 0;
        while (valid !== 1'b1) @(negedge clk);
        @(negedge clk);
        if (sar_out !== 200) begin errors = errors + 1; $display("FAIL after held start: %0d", sar_out); end
        $display("directed tests done, errors = %0d", errors);
        $finish;
    end
endmodule
