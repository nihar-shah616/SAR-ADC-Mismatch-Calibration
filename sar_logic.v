// SAR logic for an N-bit successive-approximation ADC.
//
// One conversion = 1 clock edge with start = 1, followed by N decision edges.
// On each decision edge the comparator result decides the bit currently under test,
// and the next lower bit is set as the new trial.
//
// Timing assumption: comp_in must be valid within one clock period after sar_out changes
// (DAC settling + comparator delay). This limits the maximum clock frequency of a real design.
//
// Reset is asynchronous and active low. In a real design, de-assert it through a synchroniser.
module sar_logic #(
    parameter N = 10                    // ADC resolution in bits
)(
    input  wire         clk,
    input  wire         rst_n,          // active-low asynchronous reset
    input  wire         start,          // pulse high for one clock to start a conversion
    input  wire         comp_in,        // comparator output: 1 if Vin >= Vdac(sar_out), 0 otherwise
    output reg  [N-1:0] sar_out,        // trial code during conversion; final result once valid = 1
    output reg          valid,          // level: high from the end of a conversion until the next start
    output reg          done,           // one-clock pulse, on the same edge on which valid rises
    output wire         sample          // high while idle: the sample-and-hold may track Vin
);

    // MSB-only constant, written so that it has exactly N bits (no 32-bit integer shift)
    localparam [N-1:0] MSB = 1'b1 << (N - 1);

    reg [N-1:0] mask;                   // one-hot: the bit currently being decided (0 when idle)

    assign sample = (mask == {N{1'b0}});

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sar_out <= {N{1'b0}};
            mask    <= {N{1'b0}};
            valid   <= 1'b0;
            done    <= 1'b0;
        end else begin
            done <= 1'b0;                           // default: done is a one-cycle pulse
            if (start) begin
                // Start (or restart) a conversion: try the MSB first
                sar_out <= MSB;
                mask    <= MSB;
                valid   <= 1'b0;
            end else if (mask != 0) begin
                // Decide the bit under test from the comparator result,
                // then set the next lower bit as the new trial
                if (comp_in)
                    sar_out <= sar_out | (mask >> 1);               // keep bit = 1
                else
                    sar_out <= (sar_out & ~mask) | (mask >> 1);     // clear bit to 0

                mask <= mask >> 1;

                // Last bit (mask == 1) is being decided on this edge:
                // sar_out is already final after this edge, and valid rises with it
                if (mask == 1) begin
                    valid <= 1'b1;
                    done  <= 1'b1;
                end
            end
        end
    end

endmodule
