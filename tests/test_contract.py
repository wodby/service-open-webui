"""Render the service's value mappings against its pinned public chart, offline from Kubernetes."""
import copy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


def put(values, path, value):
    parts = path.split(".")
    for part in parts[:-1]:
        values = values.setdefault(part, {})
    values[parts[-1]] = value


class ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = yaml.safe_load((Path(__file__).parents[1] / "service.yml").read_text())
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.env = {**os.environ, "KUBECONFIG": os.devnull}
        helm = cls.manifest["helm"]
        subprocess.run(["helm", "pull", helm["chart"], "--version", str(helm["version"]),
                        "--untar", "--untardir", cls.temp.name], env=cls.env, check=True, capture_output=True)
        cls.chart = str(Path(cls.temp.name) / "stateful")

    def values(self):
        values = {}
        for entry in self.manifest["helm"]["values"]:
            put(values, entry["name"], copy.deepcopy(entry["value"]))
        for entry in self.manifest["volumes"][0]["helm"]["values"]:
            put(values, entry["name"], copy.deepcopy(entry["value"]))
        put(values, "persistence.size", "10Gi")
        put(values, "persistence.storageClass", "standard")
        mappings = self.manifest["helm"]["valueMappings"]
        put(values, mappings["replicas"], 1)
        put(values, mappings["serviceAccountName"], "chat-account")
        put(values, mappings["serviceAccountCreate"], False)
        values.update(fullnameOverride="chat")
        values["image"] = {"registry": "ghcr.io", "repository": "open-webui/open-webui", "tag": self.manifest["options"][0]["tag"]}
        # Wodby resolves its own {{...}} tokens before Helm renders the values.
        values["envVars"] = [{"name": e["name"], "value": e["value"].replace("{{service.primaryURL}}", "https://chat.example.com")}
                             for e in self.manifest["env"] if not e.get("secret")]
        return values

    def render(self, values):
        result = subprocess.run(["helm", "template", "chat", self.chart, "--namespace", "test", "-f", "-"],
                                input=yaml.safe_dump(values), text=True, env=self.env, check=True, capture_output=True)
        return {doc["kind"]: doc for doc in yaml.safe_load_all(result.stdout) if doc and doc["kind"] != "Service"}

    def container(self):
        return self.render(self.values())["StatefulSet"]["spec"]["template"]["spec"]["containers"][0]

    def test_statefulset_with_data_volume(self):
        statefulset = self.render(self.values())["StatefulSet"]
        self.assertEqual(statefulset["spec"]["replicas"], 1)
        claim = statefulset["spec"]["volumeClaimTemplates"][0]
        self.assertEqual(claim["spec"]["resources"]["requests"]["storage"], "10Gi")
        container = statefulset["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["image"], "ghcr.io/open-webui/open-webui:v0.13.0")
        self.assertIn({"name": claim["metadata"]["name"], "mountPath": "/data"},
                      [{k: m[k] for k in ("name", "mountPath")} for m in container["volumeMounts"]])
        environment = {e["name"]: e["value"] for e in container["env"]}
        self.assertEqual(environment["DATA_DIR"], "/data")
        self.assertTrue(environment["HOME"].startswith("/data/"))
        for name in ["HF_HOME", "SENTENCE_TRANSFORMERS_HOME", "WHISPER_MODEL_DIR", "TIKTOKEN_CACHE_DIR"]:
            self.assertTrue(environment[name].startswith("/data/cache/"), name)

    def test_runs_as_non_root_in_group_zero(self):
        statefulset = self.render(self.values())["StatefulSet"]
        pod = statefulset["spec"]["template"]["spec"]
        self.assertEqual(pod["securityContext"]["fsGroup"], 0)
        context = pod["containers"][0]["securityContext"]
        self.assertTrue(context["runAsNonRoot"])
        self.assertNotEqual(context["runAsUser"], 0)
        self.assertEqual(context["runAsGroup"], 0)

    def test_probes(self):
        container = self.container()
        self.assertEqual(container["startupProbe"]["httpGet"]["path"], "/health")
        self.assertEqual(container["livenessProbe"]["httpGet"]["path"], "/health")
        self.assertEqual(container["readinessProbe"]["httpGet"]["path"], "/ready")

    def test_secrets_and_required_settings(self):
        self.assertTrue(next(e for e in self.manifest["env"] if e["name"] == "WEBUI_SECRET_KEY")["secret"])
        settings = {s["var"]: s for s in self.manifest["settings"]}
        self.assertTrue(settings["WEBUI_ADMIN_EMAIL"]["required"])
        self.assertTrue(settings["WEBUI_ADMIN_PASSWORD"]["required"])
        self.assertTrue(settings["WEBUI_ADMIN_PASSWORD"]["secret"])
        links = {link["name"]: link for link in self.manifest["links"]}
        self.assertTrue(links["postgres"]["required"])
        link_env = {e["name"]: e for link in links.values() for e in link["env"]}
        self.assertTrue(link_env["DATABASE_URL"]["secret"])
        self.assertTrue(link_env["OPENAI_API_KEY"]["secret"])
        self.assertTrue(self.manifest["workloads"][0]["containers"][0]["routeMetadata"])

    def run_entrypoint(self, environment):
        """Run the container command against a stub start.sh that prints the resulting CORS origins."""
        container = self.container()
        with tempfile.TemporaryDirectory() as workdir:
            Path(workdir, "start.sh").write_text('printf "%s" "${CORS_ALLOW_ORIGIN-<unset>}"\n')
            env = {"PATH": os.environ["PATH"], "HOME": str(Path(workdir, "home")), "DATA_DIR": str(Path(workdir, "data")), **environment}
            result = subprocess.run(container["command"] + container["args"], cwd=workdir, env=env,
                                    text=True, check=True, capture_output=True)
            self.assertTrue(Path(workdir, "home").is_dir())
            self.assertTrue(Path(workdir, "data", "cache").is_dir())
            return result.stdout

    def test_cors_origins_follow_routed_hosts(self):
        self.assertEqual(self.run_entrypoint({"WODBY_HOSTS": '["chat.example.com","www.example.com"]'}),
                         "https://chat.example.com;http://chat.example.com;https://www.example.com;http://www.example.com")
        self.assertEqual(self.run_entrypoint({"WODBY_HOSTS": "[]"}), "<unset>")
        self.assertEqual(self.run_entrypoint({}), "<unset>")
        self.assertEqual(self.run_entrypoint({"WODBY_HOSTS": '["a.example.com"]', "CORS_ALLOW_ORIGIN": "https://own"}), "https://own")


if __name__ == "__main__":
    unittest.main()
