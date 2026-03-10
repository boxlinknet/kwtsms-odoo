/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class KwtSmsTestWidget extends Component {
    static template = "kwtsms_sms.TestSmsWidget";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            phone: "",
            message: `kwtSMS gateway test from Odoo at ${new Date().toLocaleString()}`,
            sending: false,
            resultMessage: "",
            resultType: "", // "success" or "danger"
        });
    }

    onPhoneInput(ev) {
        this.state.phone = ev.target.value;
        this.state.resultMessage = "";
        this.state.resultType = "";
    }

    onMessageInput(ev) {
        this.state.message = ev.target.value;
        this.state.resultMessage = "";
        this.state.resultType = "";
    }

    async onClickSend() {
        this.state.resultMessage = "";
        this.state.resultType = "";

        if (!this.state.phone) {
            this.state.resultMessage = "Please enter a phone number.";
            this.state.resultType = "danger";
            return;
        }
        if (!this.state.message) {
            this.state.resultMessage = "Please enter a message.";
            this.state.resultType = "danger";
            return;
        }

        this.state.sending = true;
        try {
            const result = await this.orm.call(
                "res.config.settings",
                "action_kwtsms_send_test_rpc",
                [],
                { phone: this.state.phone, message: this.state.message }
            );
            this.state.resultMessage = result.message;
            this.state.resultType = result.success ? "success" : "danger";
        } catch (e) {
            this.state.resultMessage = "Failed to send test SMS.";
            this.state.resultType = "danger";
        }
        this.state.sending = false;
    }
}

const kwtsmsTestSmsWidget = {
    component: KwtSmsTestWidget,
};

registry.category("view_widgets").add("kwtsms_test_sms", kwtsmsTestSmsWidget);
