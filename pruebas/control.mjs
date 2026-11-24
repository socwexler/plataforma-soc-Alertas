// Cifras esperadas de la bitácora real: archivo local, fuera del repositorio
import fs from "fs";
if (!process.env.SOC_CONTROL) { console.log("Defina SOC_CONTROL con la ruta de control.json"); process.exit(1); }
export default JSON.parse(fs.readFileSync(process.env.SOC_CONTROL, "utf8"));
