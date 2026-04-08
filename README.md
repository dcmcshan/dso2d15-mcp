# dso2d15-mcp

A [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server for the **Hantek DSO2D15** (and other **DSO2000**-family scopes) using **USB** and **SCPI** over **PyVISA** (`pyvisa-py` backend by default).

Official SCPI reference: [DSO2000 Series SCPI Programmer’s Manual (PDF)](https://www.hantek.com/uploadpic/hantek/files/20211231/DSO2000%20Series%C2%A0SCPI%C2%A0Programmers%C2%A0Manual.pdf).

Waveform acquisition follows the same `PRIVate:WAVeform:DATA:ALL?` flow used in community tooling ([hantek-dso2000](https://github.com/phmarek/hantek-dso2000)).

## Requirements

- Python 3.10+
- USB connection to the scope (rear USB device port)
- OS support for USB-TMC via PyVISA:
  - **Linux**: often works with `usbcore` / `usbtmc` kernel driver or libusb stack used by `pyvisa-py`
  - **macOS**: install includes **`pyusb`** so `pyvisa-py` can enumerate USB-TMC. If discovery still fails, try [NI-VISA](https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html) and `DSO2D15_VISA_BACKEND=@ni`.

**DSO2D15 USB IDs** (matches VISA `USB0::1183::20574::…`): Vendor **0x049F** (1183), Product **0x505E** (20574). Example serial: `CN5546029098237` → resource like `USB0::1183::20574::CN5546029098237::0::INSTR`.

If opening the instrument fails with **`usb.core.USBError: … Access denied (insufficient permissions)`** on macOS, `pyvisa-py` cannot claim the USB-TMC interface via libusb. Install **NI-VISA**, set `DSO2D15_VISA_BACKEND=@ni`, and use the NI resource string, or fix libusb access for that device (vendor docs / system USB policy).

## Install

```bash
cd dso2d15-mcp
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Run the server (stdio transport for Cursor/Claude Desktop):

```bash
dso2d15-mcp
# or
python -m dso2d15_mcp.server
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `DSO2D15_VISA` | Full VISA resource string, e.g. `USB0::0x049F::0x505E::...::INSTR` (use `dso2d15_list_visa_resources` to discover) |
| `DSO2D15_VISA_QUERY` | Pattern for auto-pick when `DSO2D15_VISA` is unset. Default: `USB0::1183::20574:?*` (Hantek DSO2000 IDs used by common tooling) |
| `DSO2D15_TIMEOUT_MS` | VISA read timeout in ms (default `120000`; large captures can be slow) |
| `DSO2D15_VISA_BACKEND` | PyVISA resource manager string (default `@py` for `pyvisa-py`) |

## Cursor MCP configuration

Add to your MCP settings (adjust the path):

```json
{
  "mcpServers": {
    "dso2d15": {
      "command": "/absolute/path/to/dso2d15-mcp/.venv/bin/dso2d15-mcp",
      "env": {
        "DSO2D15_VISA": "USB0::...your resource...::INSTR"
      }
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `dso2d15_list_visa_resources` | List VISA resources (`query` parameter, default `?*`) |
| `dso2d15_list_hantek_candidates` | List resources matching `DSO2D15_VISA_QUERY` |
| `dso2d15_identify` | `*IDN?` |
| `dso2d15_scpi_write` | Send a SCPI command with no query response |
| `dso2d15_scpi_query` | ASCII query (responses that are not binary blocks) |
| `dso2d15_scpi_query_binary` | Binary/block responses (returns length + base64 preview) |
| `dso2d15_fetch_waveform` | High-level waveform JSON via `PRIVate:WAVeform:DATA:ALL?` |

Use `dso2d15_scpi_query` for interactive exploration (examples: `*IDN?`, `:CHANnel1:SCALe?`, `:TIMebase:MAIN:SCALe?`). Refer to the Hantek PDF for the full command set.

## License

MIT
